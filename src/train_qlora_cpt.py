#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Continued pretraining on your Markdown corpus using QLoRA (4-bit) for 3B models.

Recommended base model for RTX 2070 Super (8 GB VRAM):
  - Qwen/Qwen2.5-3B-Instruct (works for both CPT and chat inference)

This script trains on plain text where each line is treated as continuation.
Use build_corpus.py to produce a single text file from chunks.jsonl.
"""

import argparse
import os
from dataclasses import dataclass

import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import BitsAndBytesConfig


@dataclass
class Args:
    model_name: str
    corpus_path: str
    output_dir: str
    lr: float
    epochs: int
    per_device_train_batch_size: int
    gradient_accumulation_steps: int
    max_seq_len: int
    seed: int


def parse_args() -> Args:
    p = argparse.ArgumentParser(description='QLoRA continued pretraining on Markdown corpus')
    p.add_argument('--model', default='Qwen/Qwen2.5-3B-Instruct')
    p.add_argument('--corpus', required=True, help='Path to text corpus file (from build_corpus.py)')
    p.add_argument('--out', default='./outputs/qlora-cpt')
    p.add_argument('--lr', type=float, default=1e-4)
    p.add_argument('--epochs', type=int, default=2)
    p.add_argument('--bsz', type=int, default=1, help='per-device batch size')
    p.add_argument('--grad-accum', type=int, default=16)
    p.add_argument('--max-seq-len', type=int, default=2048)
    p.add_argument('--seed', type=int, default=42)
    a = p.parse_args()
    return Args(
        model_name=a.model,
        corpus_path=a.corpus,
        output_dir=a.out,
        lr=a.lr,
        epochs=a.epochs,
        per_device_train_batch_size=a.bsz,
        gradient_accumulation_steps=a.grad_accum,
        max_seq_len=a.max_seq_len,
        seed=a.seed,
    )


def main():
    args = parse_args()

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type='nf4',
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        quantization_config=bnb_config,
        device_map='auto',
    )
    model = prepare_model_for_kbit_training(model)
    # Trainer will set this, but do it early to silence warnings
    if hasattr(model, 'config'):
        model.config.use_cache = False
    # Optional: enable grad checkpointing to save VRAM
    if hasattr(model, 'gradient_checkpointing_enable'):
        try:
            model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        except TypeError:
            model.gradient_checkpointing_enable()
    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias='none',
        task_type='CAUSAL_LM',
        target_modules=[
            'q_proj', 'k_proj', 'v_proj', 'o_proj',
            'gate_proj', 'up_proj', 'down_proj'
        ],
    )
    model = get_peft_model(model, peft_config)

    dataset = load_dataset('text', data_files={'train': args.corpus_path})

    def tokenize_fn(batch):
        return tokenizer(batch['text'], truncation=True, max_length=args.max_seq_len, return_attention_mask=True)

    tokenized = dataset.map(tokenize_fn, batched=True, remove_columns=['text'])
    # Remove any empty tokenized samples
    tokenized = tokenized.filter(lambda ex: len(ex.get('input_ids', [])) > 0)

    # Concatenate and chunk into fixed-length blocks for causal LM
    from itertools import chain
    block_size = args.max_seq_len

    def group_texts(examples):
        concatenated = {k: list(chain(*examples[k])) for k in examples}
        total_length = len(concatenated['input_ids'])
        if total_length < block_size:
            return {k: [] for k in concatenated}
        total_length = (total_length // block_size) * block_size
        result = {k: [t[i:i + block_size] for i in range(0, total_length, block_size)] for k, t in concatenated.items()}
        result['labels'] = result['input_ids'].copy()
        return result

    lm_dataset = tokenized.map(group_texts, batched=True)

    class IntCastingCollator(DataCollatorForLanguageModeling):
        def __call__(self, examples):
            batch = super().__call__(examples)
            for key in ('input_ids', 'labels', 'attention_mask'):
                if key in batch and batch[key] is not None and batch[key].dtype != torch.long:
                    batch[key] = batch[key].long()
            return batch

    collator = IntCastingCollator(tokenizer=tokenizer, mlm=False)

    # Choose precision: prefer bf16 if supported (Ampere+), else fp16 if CUDA available
    use_bf16 = bool(torch.cuda.is_available() and getattr(torch.cuda, 'is_bf16_supported', lambda: False)())
    use_fp16 = bool(torch.cuda.is_available() and not use_bf16)

    train_args = TrainingArguments(
        output_dir=args.output_dir,
        learning_rate=args.lr,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.per_device_train_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        logging_steps=10,
        save_steps=200,
        save_total_limit=2,
        bf16=use_bf16,
        fp16=use_fp16,
        seed=args.seed,
        dataloader_pin_memory=False,
        report_to=[],
        # Memory optimization for RTX 2070 Super
        gradient_checkpointing=True,
        dataloader_num_workers=0,  # Reduce CPU->GPU transfer overhead
        remove_unused_columns=False,
        optim="paged_adamw_8bit",  # 8-bit optimizer to save memory
    )

    trainer = Trainer(
        model=model,
        args=train_args,
        train_dataset=lm_dataset['train'],
        data_collator=collator,
    )

    trainer.train()
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    print(f"Saved LoRA adapter and tokenizer to {args.output_dir}")


if __name__ == '__main__':
    main()


