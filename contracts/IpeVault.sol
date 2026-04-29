// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract IpeVault {
    address public backendSystem;
    uint256 public requiredSignatures;

    mapping(address => bool) public isSigner;
    address[] public signers;

    struct Proposal {
        uint256 id;
        address recipient;
        uint256 amount;
        uint256 approvalCount;
        bool executed;
    }
    
    // Nested mapping for signatures (id => signer => bool)
    mapping(uint256 => mapping(address => bool)) public hasSigned;

    uint256 public proposalCount;
    mapping(uint256 => Proposal) public proposals;

    event Deposited(address indexed sender, uint256 amount);
    event ProposalSubmitted(uint256 indexed id, address indexed recipient, uint256 amount);
    event ProposalApproved(uint256 indexed id, address indexed signer);
    event Claimed(uint256 indexed id, address indexed recipient, uint256 amount);

    constructor(address[] memory _signers, uint256 _requiredSignatures) {
        backendSystem = msg.sender;
        require(_requiredSignatures <= _signers.length && _requiredSignatures > 0, "Requisitos invalidos");
        
        for (uint i = 0; i < _signers.length; i++) {
            require(_signers[i] != address(0), "Enderecos nulos proibidos");
            isSigner[_signers[i]] = true;
            signers.push(_signers[i]);
        }
        requiredSignatures = _requiredSignatures;
    }

    modifier onlyBackend() {
        require(msg.sender == backendSystem, "Unicamente a IA pode submeter");
        _;
    }

    modifier onlySigner() {
        require(isSigner[msg.sender], "Apenas signatarios do comite");
        _;
    }

    function deposit() external payable {
        emit Deposited(msg.sender, msg.value);
    }
    
    receive() external payable {
        emit Deposited(msg.sender, msg.value);
    }

    // Etapa 1: A IA submete o resultado do consenso
    function submitGrant(address _recipient, uint256 _amount) external onlyBackend returns (uint256) {
        require(_recipient != address(0), "Endereco invalido");

        uint256 id = proposalCount;
        Proposal storage p = proposals[id];
        p.id = id;
        p.recipient = _recipient;
        p.amount = _amount;
        p.approvalCount = 0;
        p.executed = false;

        proposalCount++;
        emit ProposalSubmitted(id, _recipient, _amount);
        return id;
    }

    // Etapa 2: Humanos assinam via frontend (ou etherscan)
    function approveGrant(uint256 _id) external onlySigner {
        Proposal storage p = proposals[_id];
        require(!p.executed, "Ja executado");
        require(!hasSigned[_id][msg.sender], "Ja assinado por esta wallet");

        hasSigned[_id][msg.sender] = true;
        p.approvalCount++;

        emit ProposalApproved(_id, msg.sender);
    }

    // Etapa 3: Resgate pull-over-push
    function claim(uint256 _id) external {
        Proposal storage p = proposals[_id];
        require(!p.executed, "Ja executado");
        require(p.approvalCount >= requiredSignatures, "Faltam assinaturas");
        require(address(this).balance >= p.amount, "Liquidez insuficiente");
        
        p.executed = true; // Previne reentrancy

        (bool success, ) = p.recipient.call{value: p.amount}("");
        require(success, "Falha ao enviar valor financeiro");

        emit Claimed(_id, p.recipient, p.amount);
    }
}
