from flask import Blueprint, request, jsonify
from src.models.user import db, Cliente, Brinde, Resgate, Ponto, StatusResgateEnum, NivelEnum
from datetime import datetime
import uuid
import secrets

resgate_bp = Blueprint('resgate', __name__)

def gerar_voucher_codigo():
    """Gera um código único para o voucher"""
    return f"VCH-{secrets.token_hex(4).upper()}-{datetime.now().strftime('%Y%m%d')}"

def verificar_elegibilidade_cliente(cliente_id, brinde_id):
    """Verifica se o cliente é elegível para resgatar o brinde"""
    try:
        cliente = Cliente.query.get(cliente_id)
        if not cliente:
            return False, "Cliente não encontrado"
        
        brinde = Brinde.query.get(brinde_id)
        if not brinde:
            return False, "Brinde não encontrado"
        
        # Verificar se a campanha está ativa
        if not brinde.campanha.ativa:
            return False, "Campanha não está ativa"
        
        # Verificar se está dentro do período da campanha
        agora = datetime.utcnow()
        if agora < brinde.campanha.data_inicio or agora > brinde.campanha.data_fim:
            return False, "Campanha fora do período de validade"
        
        # Verificar disponibilidade do brinde
        if brinde.quantidade_disponivel <= 0:
            return False, "Brinde não disponível"
        
        # Verificar pontos do cliente
        ponto = Ponto.query.filter_by(cliente_id=cliente_id).first()
        if not ponto:
            return False, "Cliente não possui pontos registrados"
        
        # Verificar se o nível do cliente permite o brinde
        nivel_cliente = ponto.nivel_atual
        nivel_brinde = brinde.nivel
        
        # Hierarquia: Bronze < Prata < Ouro
        niveis_hierarquia = {
            NivelEnum.BRONZE: 1,
            NivelEnum.PRATA: 2,
            NivelEnum.OURO: 3
        }
        
        if niveis_hierarquia[nivel_cliente] < niveis_hierarquia[nivel_brinde]:
            return False, f"Nível insuficiente. Necessário: {nivel_brinde.value}, Atual: {nivel_cliente.value}"
        
        # Verificar threshold de visitas se configurado
        total_visitas = len(cliente.visitas)
        if total_visitas < brinde.campanha.threshold_visitas:
            return False, f"Número de visitas insuficiente. Necessário: {brinde.campanha.threshold_visitas}, Atual: {total_visitas}"
        
        return True, "Cliente elegível"
        
    except Exception as e:
        return False, f"Erro ao verificar elegibilidade: {str(e)}"

@resgate_bp.route('/resgates/verificar-elegibilidade', methods=['POST'])
def verificar_elegibilidade():
    """Verifica se um cliente pode resgatar um brinde"""
    try:
        data = request.get_json()
        
        if not data.get('cliente_id') or not data.get('brinde_id'):
            return jsonify({'error': 'cliente_id e brinde_id são obrigatórios'}), 400
        
        elegivel, mensagem = verificar_elegibilidade_cliente(
            data['cliente_id'], 
            data['brinde_id']
        )
        
        return jsonify({
            'elegivel': elegivel,
            'mensagem': mensagem
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@resgate_bp.route('/resgates', methods=['POST'])
def criar_resgate():
    """Cria um novo resgate de brinde"""
    try:
        data = request.get_json()
        
        if not data.get('cliente_id') or not data.get('brinde_id'):
            return jsonify({'error': 'cliente_id e brinde_id são obrigatórios'}), 400
        
        cliente_id = data['cliente_id']
        brinde_id = data['brinde_id']
        
        # Verificar elegibilidade
        elegivel, mensagem = verificar_elegibilidade_cliente(cliente_id, brinde_id)
        if not elegivel:
            return jsonify({'error': mensagem}), 400
        
        # Verificar se já existe resgate pendente para este cliente e brinde
        resgate_existente = Resgate.query.filter_by(
            cliente_id=cliente_id,
            brinde_id=brinde_id,
            status=StatusResgateEnum.PENDENTE
        ).first()
        
        if resgate_existente:
            return jsonify({'error': 'Já existe um resgate pendente para este brinde'}), 400
        
        # Criar resgate
        voucher_codigo = gerar_voucher_codigo()
        
        resgate = Resgate(
            cliente_id=cliente_id,
            brinde_id=brinde_id,
            voucher_codigo=voucher_codigo,
            status=StatusResgateEnum.PENDENTE
        )
        
        db.session.add(resgate)
        
        # Reduzir quantidade disponível do brinde
        brinde = Brinde.query.get(brinde_id)
        brinde.quantidade_disponivel -= 1
        
        db.session.commit()
        
        return jsonify(resgate.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@resgate_bp.route('/resgates/<int:resgate_id>/entregar', methods=['PUT'])
def entregar_brinde(resgate_id):
    """Marca um brinde como entregue"""
    try:
        resgate = Resgate.query.get_or_404(resgate_id)
        
        if resgate.status != StatusResgateEnum.PENDENTE:
            return jsonify({'error': 'Resgate não está pendente'}), 400
        
        resgate.status = StatusResgateEnum.ENTREGUE
        resgate.data_entrega = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify(resgate.to_dict())
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@resgate_bp.route('/resgates/<int:resgate_id>/cancelar', methods=['PUT'])
def cancelar_resgate(resgate_id):
    """Cancela um resgate"""
    try:
        resgate = Resgate.query.get_or_404(resgate_id)
        
        if resgate.status == StatusResgateEnum.ENTREGUE:
            return jsonify({'error': 'Não é possível cancelar resgate já entregue'}), 400
        
        # Devolver quantidade ao brinde
        if resgate.status == StatusResgateEnum.PENDENTE:
            brinde = Brinde.query.get(resgate.brinde_id)
            brinde.quantidade_disponivel += 1
        
        resgate.status = StatusResgateEnum.CANCELADO
        
        db.session.commit()
        
        return jsonify(resgate.to_dict())
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@resgate_bp.route('/resgates/cliente/<int:cliente_id>', methods=['GET'])
def listar_resgates_cliente(cliente_id):
    """Lista todos os resgates de um cliente"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status_filter = request.args.get('status')
        
        query = Resgate.query.filter_by(cliente_id=cliente_id)
        
        if status_filter:
            try:
                status_enum = StatusResgateEnum(status_filter)
                query = query.filter(Resgate.status == status_enum)
            except ValueError:
                return jsonify({'error': 'Status inválido'}), 400
        
        resgates = query.order_by(Resgate.data_resgate.desc())\
                       .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'resgates': [resgate.to_dict() for resgate in resgates.items],
            'total': resgates.total,
            'pages': resgates.pages,
            'current_page': page
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@resgate_bp.route('/resgates', methods=['GET'])
def listar_resgates():
    """Lista todos os resgates com filtros"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status_filter = request.args.get('status')
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        
        query = Resgate.query
        
        if status_filter:
            try:
                status_enum = StatusResgateEnum(status_filter)
                query = query.filter(Resgate.status == status_enum)
            except ValueError:
                return jsonify({'error': 'Status inválido'}), 400
        
        if data_inicio:
            data_inicio = datetime.fromisoformat(data_inicio)
            query = query.filter(Resgate.data_resgate >= data_inicio)
        
        if data_fim:
            data_fim = datetime.fromisoformat(data_fim)
            query = query.filter(Resgate.data_resgate <= data_fim)
        
        resgates = query.order_by(Resgate.data_resgate.desc())\
                       .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'resgates': [resgate.to_dict() for resgate in resgates.items],
            'total': resgates.total,
            'pages': resgates.pages,
            'current_page': page
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@resgate_bp.route('/resgates/voucher/<voucher_codigo>', methods=['GET'])
def buscar_por_voucher(voucher_codigo):
    """Busca resgate por código do voucher"""
    try:
        resgate = Resgate.query.filter_by(voucher_codigo=voucher_codigo).first()
        
        if not resgate:
            return jsonify({'error': 'Voucher não encontrado'}), 404
        
        return jsonify(resgate.to_dict())
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@resgate_bp.route('/resgates/brindes-disponiveis/<int:cliente_id>', methods=['GET'])
def listar_brindes_disponiveis(cliente_id):
    """Lista brindes disponíveis para um cliente"""
    try:
        cliente = Cliente.query.get(cliente_id)
        if not cliente:
            return jsonify({'error': 'Cliente não encontrado'}), 404
        
        # Buscar campanhas ativas
        agora = datetime.utcnow()
        campanhas_ativas = db.session.query(Brinde)\
                                   .join(Brinde.campanha)\
                                   .filter(
                                       Brinde.quantidade_disponivel > 0,
                                       Brinde.campanha.has(ativa=True),
                                       Brinde.campanha.has(data_inicio <= agora),
                                       Brinde.campanha.has(data_fim >= agora)
                                   ).all()
        
        brindes_disponiveis = []
        
        for brinde in campanhas_ativas:
            elegivel, mensagem = verificar_elegibilidade_cliente(cliente_id, brinde.id)
            
            brinde_dict = brinde.to_dict()
            brinde_dict['elegivel'] = elegivel
            brinde_dict['mensagem_elegibilidade'] = mensagem
            
            brindes_disponiveis.append(brinde_dict)
        
        return jsonify({
            'brindes_disponiveis': brindes_disponiveis,
            'cliente': cliente.to_dict()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

