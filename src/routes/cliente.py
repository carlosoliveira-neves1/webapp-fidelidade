from flask import Blueprint, request, jsonify
from src.models.user import db, Cliente, Visita, Ponto, NivelEnum
from datetime import datetime
import re

cliente_bp = Blueprint('cliente', __name__)

def validar_cpf(cpf):
    """Validação básica de CPF (apenas formato)"""
    cpf = re.sub(r'[^0-9]', '', cpf)
    return len(cpf) == 11 and cpf.isdigit()

def calcular_nivel_por_pontos(pontos):
    """Calcula o nível baseado na pontuação"""
    if pontos >= 1000:
        return NivelEnum.OURO
    elif pontos >= 500:
        return NivelEnum.PRATA
    else:
        return NivelEnum.BRONZE

@cliente_bp.route('/clientes', methods=['GET'])
def listar_clientes():
    """Lista todos os clientes com filtros opcionais"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        nome_filter = request.args.get('nome', '')
        cpf_filter = request.args.get('cpf', '')
        
        query = Cliente.query
        
        if nome_filter:
            query = query.filter(Cliente.nome.ilike(f'%{nome_filter}%'))
        if cpf_filter:
            query = query.filter(Cliente.cpf.like(f'%{cpf_filter}%'))
        
        clientes = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'clientes': [cliente.to_dict() for cliente in clientes.items],
            'total': clientes.total,
            'pages': clientes.pages,
            'current_page': page
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@cliente_bp.route('/clientes', methods=['POST'])
def criar_cliente():
    """Cria um novo cliente"""
    try:
        data = request.get_json()
        
        # Validações
        if not data.get('cpf') or not data.get('nome') or not data.get('telefone'):
            return jsonify({'error': 'CPF, nome e telefone são obrigatórios'}), 400
        
        cpf = re.sub(r'[^0-9]', '', data['cpf'])
        if not validar_cpf(cpf):
            return jsonify({'error': 'CPF inválido'}), 400
        
        # Verificar se CPF já existe
        cliente_existente = Cliente.query.filter_by(cpf=cpf).first()
        if cliente_existente:
            return jsonify({'error': 'CPF já cadastrado'}), 400
        
        # Criar cliente
        cliente = Cliente(
            cpf=cpf,
            nome=data['nome'],
            telefone=data['telefone'],
            email=data.get('email') if not data.get('sem_email') else None,
            sem_email=data.get('sem_email', False)
        )
        
        db.session.add(cliente)
        db.session.flush()  # Para obter o ID
        
        # Criar registro de pontos inicial
        ponto = Ponto(
            cliente_id=cliente.id,
            pontos_acumulados=0,
            nivel_atual=NivelEnum.BRONZE
        )
        
        db.session.add(ponto)
        db.session.commit()
        
        return jsonify(cliente.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@cliente_bp.route('/clientes/<int:cliente_id>', methods=['GET'])
def obter_cliente(cliente_id):
    """Obtém um cliente específico"""
    try:
        cliente = Cliente.query.get_or_404(cliente_id)
        
        # Incluir informações detalhadas
        cliente_dict = cliente.to_dict()
        cliente_dict['visitas_detalhes'] = [visita.to_dict() for visita in cliente.visitas]
        cliente_dict['pontos_detalhes'] = [ponto.to_dict() for ponto in cliente.pontos]
        
        return jsonify(cliente_dict)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@cliente_bp.route('/clientes/<int:cliente_id>', methods=['PUT'])
def atualizar_cliente(cliente_id):
    """Atualiza um cliente existente"""
    try:
        cliente = Cliente.query.get_or_404(cliente_id)
        data = request.get_json()
        
        # Validações
        if 'cpf' in data:
            cpf = re.sub(r'[^0-9]', '', data['cpf'])
            if not validar_cpf(cpf):
                return jsonify({'error': 'CPF inválido'}), 400
            
            # Verificar se CPF já existe (exceto o próprio cliente)
            cliente_existente = Cliente.query.filter(
                Cliente.cpf == cpf, 
                Cliente.id != cliente_id
            ).first()
            if cliente_existente:
                return jsonify({'error': 'CPF já cadastrado para outro cliente'}), 400
            
            cliente.cpf = cpf
        
        if 'nome' in data:
            cliente.nome = data['nome']
        if 'telefone' in data:
            cliente.telefone = data['telefone']
        if 'email' in data:
            cliente.email = data['email'] if not data.get('sem_email') else None
        if 'sem_email' in data:
            cliente.sem_email = data['sem_email']
            if data['sem_email']:
                cliente.email = None
        
        db.session.commit()
        return jsonify(cliente.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@cliente_bp.route('/clientes/<int:cliente_id>', methods=['DELETE'])
def excluir_cliente(cliente_id):
    """Exclui um cliente"""
    try:
        cliente = Cliente.query.get_or_404(cliente_id)
        
        # Verificar se há resgates pendentes
        from src.models.user import Resgate, StatusResgateEnum
        resgates_pendentes = Resgate.query.filter_by(
            cliente_id=cliente_id,
            status=StatusResgateEnum.PENDENTE
        ).count()
        
        if resgates_pendentes > 0:
            return jsonify({'error': 'Não é possível excluir cliente com resgates pendentes'}), 400
        
        db.session.delete(cliente)
        db.session.commit()
        
        return jsonify({'message': 'Cliente excluído com sucesso'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@cliente_bp.route('/clientes/buscar-cpf/<cpf>', methods=['GET'])
def buscar_por_cpf(cpf):
    """Busca cliente por CPF"""
    try:
        cpf = re.sub(r'[^0-9]', '', cpf)
        cliente = Cliente.query.filter_by(cpf=cpf).first()
        
        if not cliente:
            return jsonify({'error': 'Cliente não encontrado'}), 404
        
        return jsonify(cliente.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

