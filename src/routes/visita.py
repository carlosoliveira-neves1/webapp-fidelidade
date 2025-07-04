from flask import Blueprint, request, jsonify
from src.models.user import db, Cliente, Visita, Ponto, NivelEnum, LojaEnum, Campanha
from datetime import datetime
import re

visita_bp = Blueprint('visita', __name__)

def calcular_nivel_por_pontos(pontos):
    """Calcula o nível baseado na pontuação"""
    if pontos >= 1000:
        return NivelEnum.OURO
    elif pontos >= 500:
        return NivelEnum.PRATA
    else:
        return NivelEnum.BRONZE

def atualizar_pontos_cliente(cliente_id, valor_compra, loja=None):
    """Atualiza os pontos do cliente baseado na compra"""
    try:
        # Buscar campanha ativa para a loja ou global
        campanha = None
        if loja:
            campanha = Campanha.query.filter(
                Campanha.loja == loja,
                Campanha.ativa == True,
                Campanha.data_inicio <= datetime.utcnow(),
                Campanha.data_fim >= datetime.utcnow()
            ).first()
        
        if not campanha:
            # Buscar campanha global
            campanha = Campanha.query.filter(
                Campanha.loja.is_(None),
                Campanha.ativa == True,
                Campanha.data_inicio <= datetime.utcnow(),
                Campanha.data_fim >= datetime.utcnow()
            ).first()
        
        # Usar fator padrão se não houver campanha
        fator_pontuacao = campanha.fator_pontuacao if campanha else 1.0
        
        # Calcular pontos da compra
        pontos_compra = int(valor_compra * fator_pontuacao)
        
        # Buscar ou criar registro de pontos do cliente
        ponto = Ponto.query.filter_by(cliente_id=cliente_id).first()
        if not ponto:
            ponto = Ponto(
                cliente_id=cliente_id,
                pontos_acumulados=0,
                nivel_atual=NivelEnum.BRONZE
            )
            db.session.add(ponto)
        
        # Atualizar pontos
        ponto.pontos_acumulados += pontos_compra
        ponto.nivel_atual = calcular_nivel_por_pontos(ponto.pontos_acumulados)
        ponto.data_atualizacao = datetime.utcnow()
        
        return pontos_compra
    except Exception as e:
        raise e

@visita_bp.route('/visitas', methods=['POST'])
def registrar_visita():
    """Registra uma nova visita e atualiza pontos"""
    try:
        data = request.get_json()
        
        # Validações
        if not data.get('cliente_id') or not data.get('valor_compra'):
            return jsonify({'error': 'cliente_id e valor_compra são obrigatórios'}), 400
        
        cliente_id = data['cliente_id']
        valor_compra = float(data['valor_compra'])
        
        if valor_compra <= 0:
            return jsonify({'error': 'Valor da compra deve ser maior que zero'}), 400
        
        # Verificar se cliente existe
        cliente = Cliente.query.get(cliente_id)
        if not cliente:
            return jsonify({'error': 'Cliente não encontrado'}), 404
        
        # Processar loja se fornecida
        loja = None
        if data.get('loja'):
            try:
                loja = LojaEnum(data['loja'])
            except ValueError:
                return jsonify({'error': 'Loja inválida'}), 400
        
        # Criar visita
        visita = Visita(
            cliente_id=cliente_id,
            valor_compra=valor_compra,
            loja=loja,
            data_visita=datetime.utcnow()
        )
        
        db.session.add(visita)
        db.session.flush()
        
        # Atualizar pontos
        pontos_ganhos = atualizar_pontos_cliente(cliente_id, valor_compra, loja)
        
        db.session.commit()
        
        # Retornar informações da visita e pontos atualizados
        ponto = Ponto.query.filter_by(cliente_id=cliente_id).first()
        
        return jsonify({
            'visita': visita.to_dict(),
            'pontos_ganhos': pontos_ganhos,
            'pontos_totais': ponto.pontos_acumulados if ponto else 0,
            'nivel_atual': ponto.nivel_atual.value if ponto else 'Bronze'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@visita_bp.route('/visitas/cliente/<int:cliente_id>', methods=['GET'])
def listar_visitas_cliente(cliente_id):
    """Lista todas as visitas de um cliente"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Verificar se cliente existe
        cliente = Cliente.query.get(cliente_id)
        if not cliente:
            return jsonify({'error': 'Cliente não encontrado'}), 404
        
        visitas = Visita.query.filter_by(cliente_id=cliente_id)\
                             .order_by(Visita.data_visita.desc())\
                             .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'visitas': [visita.to_dict() for visita in visitas.items],
            'total': visitas.total,
            'pages': visitas.pages,
            'current_page': page,
            'cliente': cliente.to_dict()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@visita_bp.route('/visitas/<int:visita_id>', methods=['GET'])
def obter_visita(visita_id):
    """Obtém uma visita específica"""
    try:
        visita = Visita.query.get_or_404(visita_id)
        return jsonify(visita.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@visita_bp.route('/visitas/<int:visita_id>', methods=['PUT'])
def atualizar_visita(visita_id):
    """Atualiza uma visita existente"""
    try:
        visita = Visita.query.get_or_404(visita_id)
        data = request.get_json()
        
        valor_antigo = visita.valor_compra
        
        if 'valor_compra' in data:
            novo_valor = float(data['valor_compra'])
            if novo_valor <= 0:
                return jsonify({'error': 'Valor da compra deve ser maior que zero'}), 400
            visita.valor_compra = novo_valor
        
        if 'loja' in data and data['loja']:
            try:
                visita.loja = LojaEnum(data['loja'])
            except ValueError:
                return jsonify({'error': 'Loja inválida'}), 400
        
        # Se o valor mudou, recalcular pontos
        if 'valor_compra' in data and valor_antigo != visita.valor_compra:
            # Remover pontos antigos e adicionar novos
            diferenca = visita.valor_compra - valor_antigo
            atualizar_pontos_cliente(visita.cliente_id, diferenca, visita.loja)
        
        db.session.commit()
        return jsonify(visita.to_dict())
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@visita_bp.route('/visitas/<int:visita_id>', methods=['DELETE'])
def excluir_visita(visita_id):
    """Exclui uma visita"""
    try:
        visita = Visita.query.get_or_404(visita_id)
        
        # Remover pontos correspondentes
        atualizar_pontos_cliente(visita.cliente_id, -visita.valor_compra, visita.loja)
        
        db.session.delete(visita)
        db.session.commit()
        
        return jsonify({'message': 'Visita excluída com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@visita_bp.route('/pontos/cliente/<int:cliente_id>', methods=['GET'])
def obter_pontos_cliente(cliente_id):
    """Obtém informações de pontos de um cliente"""
    try:
        cliente = Cliente.query.get(cliente_id)
        if not cliente:
            return jsonify({'error': 'Cliente não encontrado'}), 404
        
        ponto = Ponto.query.filter_by(cliente_id=cliente_id).first()
        if not ponto:
            # Criar registro de pontos se não existir
            ponto = Ponto(
                cliente_id=cliente_id,
                pontos_acumulados=0,
                nivel_atual=NivelEnum.BRONZE
            )
            db.session.add(ponto)
            db.session.commit()
        
        # Calcular estatísticas
        total_visitas = len(cliente.visitas)
        valor_total_compras = sum([v.valor_compra for v in cliente.visitas])
        
        return jsonify({
            'pontos': ponto.to_dict(),
            'total_visitas': total_visitas,
            'valor_total_compras': valor_total_compras,
            'cliente': cliente.to_dict()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@visita_bp.route('/relatorio/visitas', methods=['GET'])
def relatorio_visitas():
    """Relatório de visitas com filtros"""
    try:
        # Filtros
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        loja = request.args.get('loja')
        
        query = Visita.query
        
        if data_inicio:
            data_inicio = datetime.fromisoformat(data_inicio)
            query = query.filter(Visita.data_visita >= data_inicio)
        
        if data_fim:
            data_fim = datetime.fromisoformat(data_fim)
            query = query.filter(Visita.data_visita <= data_fim)
        
        if loja:
            try:
                loja_enum = LojaEnum(loja)
                query = query.filter(Visita.loja == loja_enum)
            except ValueError:
                return jsonify({'error': 'Loja inválida'}), 400
        
        visitas = query.order_by(Visita.data_visita.desc()).all()
        
        # Estatísticas
        total_visitas = len(visitas)
        valor_total = sum([v.valor_compra for v in visitas])
        valor_medio = valor_total / total_visitas if total_visitas > 0 else 0
        
        return jsonify({
            'visitas': [visita.to_dict() for visita in visitas],
            'estatisticas': {
                'total_visitas': total_visitas,
                'valor_total': valor_total,
                'valor_medio': valor_medio
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

