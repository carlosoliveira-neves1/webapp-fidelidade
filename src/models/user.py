from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from enum import Enum

db = SQLAlchemy()

class LojaEnum(Enum):
    JABAQUARA = "Mega Loja Jabaquara"
    INDIANOPOLIS = "Indianópolis"
    MASCOTE = "Mascote"
    TATUAPE = "Tatuapé"
    PRAIA_GRANDE = "Praia Grande"
    OSASCO = "Osasco"

class NivelEnum(Enum):
    BRONZE = "Bronze"
    PRATA = "Prata"
    OURO = "Ouro"

class StatusResgateEnum(Enum):
    PENDENTE = "Pendente"
    ENTREGUE = "Entregue"
    CANCELADO = "Cancelado"

class Cliente(db.Model):
    __tablename__ = 'clientes'
    
    id = db.Column(db.Integer, primary_key=True)
    cpf = db.Column(db.String(11), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(15), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    sem_email = db.Column(db.Boolean, default=False)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    visitas = db.relationship('Visita', backref='cliente', lazy=True)
    pontos = db.relationship('Ponto', backref='cliente', lazy=True)
    resgates = db.relationship('Resgate', backref='cliente', lazy=True)

    def __repr__(self):
        return f'<Cliente {self.nome}>'

    def to_dict(self):
        return {
            'id': self.id,
            'cpf': self.cpf,
            'nome': self.nome,
            'telefone': self.telefone,
            'email': self.email,
            'sem_email': self.sem_email,
            'data_cadastro': self.data_cadastro.isoformat() if self.data_cadastro else None,
            'total_visitas': len(self.visitas),
            'pontos_totais': sum([p.pontos_acumulados for p in self.pontos])
        }

class Visita(db.Model):
    __tablename__ = 'visitas'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    data_visita = db.Column(db.DateTime, default=datetime.utcnow)
    valor_compra = db.Column(db.Float, nullable=False)
    loja = db.Column(db.Enum(LojaEnum), nullable=True)

    def __repr__(self):
        return f'<Visita {self.cliente_id} - R${self.valor_compra}>'

    def to_dict(self):
        return {
            'id': self.id,
            'cliente_id': self.cliente_id,
            'data_visita': self.data_visita.isoformat() if self.data_visita else None,
            'valor_compra': self.valor_compra,
            'loja': self.loja.value if self.loja else None
        }

class Ponto(db.Model):
    __tablename__ = 'pontos'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    pontos_acumulados = db.Column(db.Integer, default=0)
    nivel_atual = db.Column(db.Enum(NivelEnum), default=NivelEnum.BRONZE)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Ponto {self.cliente_id} - {self.pontos_acumulados}>'

    def to_dict(self):
        return {
            'id': self.id,
            'cliente_id': self.cliente_id,
            'pontos_acumulados': self.pontos_acumulados,
            'nivel_atual': self.nivel_atual.value,
            'data_atualizacao': self.data_atualizacao.isoformat() if self.data_atualizacao else None
        }

class Produto(db.Model):
    __tablename__ = 'produtos'
    
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    url_imagem = db.Column(db.String(500), nullable=True)

    def __repr__(self):
        return f'<Produto {self.nome}>'

    def to_dict(self):
        return {
            'id': self.id,
            'sku': self.sku,
            'nome': self.nome,
            'descricao': self.descricao,
            'url_imagem': self.url_imagem
        }

class Campanha(db.Model):
    __tablename__ = 'campanhas'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    loja = db.Column(db.Enum(LojaEnum), nullable=True)  # null = global
    data_inicio = db.Column(db.DateTime, nullable=False)
    data_fim = db.Column(db.DateTime, nullable=False)
    ativa = db.Column(db.Boolean, default=True)
    threshold_visitas = db.Column(db.Integer, default=5)
    fator_pontuacao = db.Column(db.Float, default=1.0)
    
    # Relacionamentos
    brindes = db.relationship('Brinde', backref='campanha', lazy=True)

    def __repr__(self):
        return f'<Campanha {self.nome}>'

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'loja': self.loja.value if self.loja else None,
            'data_inicio': self.data_inicio.isoformat() if self.data_inicio else None,
            'data_fim': self.data_fim.isoformat() if self.data_fim else None,
            'ativa': self.ativa,
            'threshold_visitas': self.threshold_visitas,
            'fator_pontuacao': self.fator_pontuacao
        }

class Brinde(db.Model):
    __tablename__ = 'brindes'
    
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    campanha_id = db.Column(db.Integer, db.ForeignKey('campanhas.id'), nullable=False)
    nivel = db.Column(db.Enum(NivelEnum), nullable=False)
    quantidade_disponivel = db.Column(db.Integer, default=0)
    
    # Relacionamentos
    produto = db.relationship('Produto', backref='brindes')

    def __repr__(self):
        return f'<Brinde {self.nivel.value}>'

    def to_dict(self):
        return {
            'id': self.id,
            'produto_id': self.produto_id,
            'campanha_id': self.campanha_id,
            'nivel': self.nivel.value,
            'quantidade_disponivel': self.quantidade_disponivel,
            'produto': self.produto.to_dict() if self.produto else None
        }

class Resgate(db.Model):
    __tablename__ = 'resgates'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    brinde_id = db.Column(db.Integer, db.ForeignKey('brindes.id'), nullable=False)
    data_resgate = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.Enum(StatusResgateEnum), default=StatusResgateEnum.PENDENTE)
    voucher_codigo = db.Column(db.String(100), unique=True, nullable=True)
    data_entrega = db.Column(db.DateTime, nullable=True)
    
    # Relacionamentos
    brinde = db.relationship('Brinde', backref='resgates')

    def __repr__(self):
        return f'<Resgate {self.cliente_id} - {self.status.value}>'

    def to_dict(self):
        return {
            'id': self.id,
            'cliente_id': self.cliente_id,
            'brinde_id': self.brinde_id,
            'data_resgate': self.data_resgate.isoformat() if self.data_resgate else None,
            'status': self.status.value,
            'voucher_codigo': self.voucher_codigo,
            'data_entrega': self.data_entrega.isoformat() if self.data_entrega else None,
            'brinde': self.brinde.to_dict() if self.brinde else None
        }

# Classe User mantida para compatibilidade com o template
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email
        }

