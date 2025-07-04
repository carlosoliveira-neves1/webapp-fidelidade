from flask import Blueprint, request, jsonify
from src.models.user import db, Campanha, Brinde, Produto, LojaEnum, NivelEnum
from datetime import datetime

campanha_bp = Blueprint('campanha', __name__)

@campanha_bp.route('/campanhas', methods=['GET'])
def listar_campanhas():
    """Lista todas as campanhas"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        ativa_filter = request.args.get('ativa')
        loja_filter = request.args.get('loja')
        
        query = Campanha.query
        
        if ativa_filter is not None:
            ativa = ativa_filter.lower() == 'true'
            query = query.filter(Campanha.ativa == ativa)
        
        if loja_filter:
            try:
                loja_enum = LojaEnum(loja_filter)
                query = query.filter(Campanha.loja == loja_enum)
            except ValueError:
                return jsonify({'error': 'Loja inválida'}), 400
        
        campanhas = query.order_by(Campanha.data_inicio.desc())\
                         .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'campanhas': [campanha.to_dict() for campanha in campanhas.items],
            'total': campanhas.total,
            'pages': campanhas.pages,
            'current_page': page
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@campanha_bp.route('/campanhas', methods=['POST'])
def criar_campanha():
    """Cria uma nova campanha"""
    try:
        data = request.get_json()
        
        # Validações
        required_fields = ['nome', 'data_inicio', 'data_fim']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} é obrigatório'}), 400
        
        data_inicio = datetime.fromisoformat(data['data_inicio'])
        data_fim = datetime.fromisoformat(data['data_fim'])
        
        if data_inicio >= data_fim:
            return jsonify({'error': 'Data de início deve ser anterior à data de fim'}), 400
        
        # Processar loja
        loja = None
        if data.get('loja'):
            try:
                loja = LojaEnum(data['loja'])
            except ValueError:
                return jsonify({'error': 'Loja inválida'}), 400
        
        # Criar campanha
        campanha = Campanha(
            nome=data['nome'],
            loja=loja,
            data_inicio=data_inicio,
            data_fim=data_fim,
            ativa=data.get('ativa', True),
            threshold_visitas=data.get('threshold_visitas', 5),
            fator_pontuacao=data.get('fator_pontuacao', 1.0)
        )
        
        db.session.add(campanha)
        db.session.commit()
        
        return jsonify(campanha.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@campanha_bp.route('/campanhas/<int:campanha_id>', methods=['GET'])
def obter_campanha(campanha_id):
    """Obtém uma campanha específica"""
    try:
        campanha = Campanha.query.get_or_404(campanha_id)
        
        # Incluir brindes da campanha
        campanha_dict = campanha.to_dict()
        campanha_dict['brindes'] = [brinde.to_dict() for brinde in campanha.brindes]
        
        return jsonify(campanha_dict)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@campanha_bp.route('/campanhas/<int:campanha_id>', methods=['PUT'])
def atualizar_campanha(campanha_id):
    """Atualiza uma campanha existente"""
    try:
        campanha = Campanha.query.get_or_404(campanha_id)
        data = request.get_json()
        
        if 'nome' in data:
            campanha.nome = data['nome']
        
        if 'data_inicio' in data:
            campanha.data_inicio = datetime.fromisoformat(data['data_inicio'])
        
        if 'data_fim' in data:
            campanha.data_fim = datetime.fromisoformat(data['data_fim'])
        
        if campanha.data_inicio >= campanha.data_fim:
            return jsonify({'error': 'Data de início deve ser anterior à data de fim'}), 400
        
        if 'loja' in data:
            if data['loja']:
                try:
                    campanha.loja = LojaEnum(data['loja'])
                except ValueError:
                    return jsonify({'error': 'Loja inválida'}), 400
            else:
                campanha.loja = None
        
        if 'ativa' in data:
            campanha.ativa = data['ativa']
        
        if 'threshold_visitas' in data:
            campanha.threshold_visitas = data['threshold_visitas']
        
        if 'fator_pontuacao' in data:
            campanha.fator_pontuacao = data['fator_pontuacao']
        
        db.session.commit()
        return jsonify(campanha.to_dict())
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@campanha_bp.route('/campanhas/<int:campanha_id>', methods=['DELETE'])
def excluir_campanha(campanha_id):
    """Exclui uma campanha"""
    try:
        campanha = Campanha.query.get_or_404(campanha_id)
        
        # Verificar se há resgates vinculados aos brindes desta campanha
        from src.models.user import Resgate
        resgates_vinculados = db.session.query(Resgate)\
                                      .join(Brinde)\
                                      .filter(Brinde.campanha_id == campanha_id)\
                                      .count()
        
        if resgates_vinculados > 0:
            return jsonify({'error': 'Não é possível excluir campanha com resgates vinculados'}), 400
        
        db.session.delete(campanha)
        db.session.commit()
        
        return jsonify({'message': 'Campanha excluída com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Rotas para Produtos
@campanha_bp.route('/produtos', methods=['GET'])
def listar_produtos():
    """Lista todos os produtos"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        nome_filter = request.args.get('nome', '')
        
        query = Produto.query
        
        if nome_filter:
            query = query.filter(Produto.nome.ilike(f'%{nome_filter}%'))
        
        produtos = query.order_by(Produto.nome)\
                       .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'produtos': [produto.to_dict() for produto in produtos.items],
            'total': produtos.total,
            'pages': produtos.pages,
            'current_page': page
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@campanha_bp.route('/produtos', methods=['POST'])
def criar_produto():
    """Cria um novo produto"""
    try:
        data = request.get_json()
        
        # Validações
        if not data.get('sku') or not data.get('nome'):
            return jsonify({'error': 'SKU e nome são obrigatórios'}), 400
        
        # Verificar se SKU já existe
        produto_existente = Produto.query.filter_by(sku=data['sku']).first()
        if produto_existente:
            return jsonify({'error': 'SKU já cadastrado'}), 400
        
        produto = Produto(
            sku=data['sku'],
            nome=data['nome'],
            descricao=data.get('descricao'),
            url_imagem=data.get('url_imagem')
        )
        
        db.session.add(produto)
        db.session.commit()
        
        return jsonify(produto.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Rotas para Brindes
@campanha_bp.route('/brindes', methods=['GET'])
def listar_brindes():
    """Lista todos os brindes"""
    try:
        campanha_id = request.args.get('campanha_id', type=int)
        nivel = request.args.get('nivel')
        
        query = Brinde.query
        
        if campanha_id:
            query = query.filter(Brinde.campanha_id == campanha_id)
        
        if nivel:
            try:
                nivel_enum = NivelEnum(nivel)
                query = query.filter(Brinde.nivel == nivel_enum)
            except ValueError:
                return jsonify({'error': 'Nível inválido'}), 400
        
        brindes = query.all()
        
        return jsonify({
            'brindes': [brinde.to_dict() for brinde in brindes]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@campanha_bp.route('/brindes', methods=['POST'])
def criar_brinde():
    """Cria um novo brinde"""
    try:
        data = request.get_json()
        
        # Validações
        required_fields = ['produto_id', 'campanha_id', 'nivel']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} é obrigatório'}), 400
        
        # Verificar se produto e campanha existem
        produto = Produto.query.get(data['produto_id'])
        if not produto:
            return jsonify({'error': 'Produto não encontrado'}), 404
        
        campanha = Campanha.query.get(data['campanha_id'])
        if not campanha:
            return jsonify({'error': 'Campanha não encontrada'}), 404
        
        # Validar nível
        try:
            nivel_enum = NivelEnum(data['nivel'])
        except ValueError:
            return jsonify({'error': 'Nível inválido'}), 400
        
        brinde = Brinde(
            produto_id=data['produto_id'],
            campanha_id=data['campanha_id'],
            nivel=nivel_enum,
            quantidade_disponivel=data.get('quantidade_disponivel', 0)
        )
        
        db.session.add(brinde)
        db.session.commit()
        
        return jsonify(brinde.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@campanha_bp.route('/brindes/<int:brinde_id>', methods=['PUT'])
def atualizar_brinde(brinde_id):
    """Atualiza um brinde existente"""
    try:
        brinde = Brinde.query.get_or_404(brinde_id)
        data = request.get_json()
        
        if 'quantidade_disponivel' in data:
            brinde.quantidade_disponivel = data['quantidade_disponivel']
        
        if 'nivel' in data:
            try:
                brinde.nivel = NivelEnum(data['nivel'])
            except ValueError:
                return jsonify({'error': 'Nível inválido'}), 400
        
        db.session.commit()
        return jsonify(brinde.to_dict())
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@campanha_bp.route('/brindes/<int:brinde_id>', methods=['DELETE'])
def excluir_brinde(brinde_id):
    """Exclui um brinde"""
    try:
        brinde = Brinde.query.get_or_404(brinde_id)
        
        # Verificar se há resgates vinculados
        from src.models.user import Resgate
        resgates_vinculados = Resgate.query.filter_by(brinde_id=brinde_id).count()
        
        if resgates_vinculados > 0:
            return jsonify({'error': 'Não é possível excluir brinde com resgates vinculados'}), 400
        
        db.session.delete(brinde)
        db.session.commit()
        
        return jsonify({'message': 'Brinde excluído com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

