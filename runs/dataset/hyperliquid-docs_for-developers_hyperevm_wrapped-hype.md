# Wrapped HYPE | Hyperliquid Docs

Copy

  1. [For developers](/hyperliquid-docs/for-developers)
  2. [HyperEVM](/hyperliquid-docs/for-developers/hyperevm)

# Wrapped HYPE

A canonical system contract for wrapped HYPE is deployed at `0x555...5`. The contract is immutable, with the same source code as wrapped ETH on Ethereum, apart from the token name and symbol. 

The source code for WHYPE is provided below. Note that this is based on the WETH contract on Ethereum mainnet and other EVM chains.

Copy
    
    
    pragma solidity >=0.4.22 <0.6;
    
    contract WHYPE9 {
      string public name = "Wrapped HYPE";
      string public symbol = "WHYPE";
      uint8 public decimals = 18;
    
      event Approval(address indexed src, address indexed guy, uint wad);
      event Transfer(address indexed src, address indexed dst, uint wad);
      event Deposit(address indexed dst, uint wad);
      event Withdrawal(address indexed src, uint wad);
    
      mapping(address => uint) public balanceOf;
      mapping(address => mapping(address => uint)) public allowance;
    
      function() external payable {
        deposit();
      }
    
      function deposit() public payable {
        balanceOf[msg.sender] += msg.value;
        emit Deposit(msg.sender, msg.value);
      }
    
      function withdraw(uint wad) public {
        require(balanceOf[msg.sender] >= wad);
        balanceOf[msg.sender] -= wad;
        msg.sender.transfer(wad);
        emit Withdrawal(msg.sender, wad);
      }
    
      function totalSupply() public view returns (uint) {
        return address(this).balance;
      }
    
      function approve(address guy, uint wad) public returns (bool) {
        allowance[msg.sender][guy] = wad;
        emit Approval(msg.sender, guy, wad);
        return true;
      }
    
      function transfer(address dst, uint wad) public returns (bool) {
        return transferFrom(msg.sender, dst, wad);
      }
    
      function transferFrom(address src, address dst, uint wad) public returns (bool) {
        require(balanceOf[src] >= wad);
    
        if (src != msg.sender && allowance[src][msg.sender] != uint(-1)) {
          require(allowance[src][msg.sender] >= wad);
          allowance[src][msg.sender] -= wad;
        }
    
        balanceOf[src] -= wad;
        balanceOf[dst] += wad;
    
        emit Transfer(src, dst, wad);
    
        return true;
      }
    }

[PreviousInteraction timings](/hyperliquid-docs/for-developers/hyperevm/interaction-timings)[NextJSON-RPC](/hyperliquid-docs/for-developers/hyperevm/json-rpc)

Last updated 6 months ago