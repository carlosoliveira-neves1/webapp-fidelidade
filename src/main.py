import os
import sys
from dotenv import load_dotenv
from flask import Flask, send_from_directory
from flask_cors import CORS

# Permite imports relativos à raiz do projeto
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Carrega variáveis de ambiente do .env
load_dotenv()

# Importa db e blueprints
from src.models.user import db
from src.routes.user import user_bp
from src.routes.cliente import cliente_bp
from src.routes.visita import visita_bp
from src.routes.campanha import campanha_bp
from src.routes.resgate import resgate_bp
from src.routes.dashboard import dashboard_bp

# Cria app e configura pasta estática (frontend build)
app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), 'static')
)

# Configurações gerais
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'changeme123!')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'postgresql://postgress:Casadocigano%402025@localhost:5432/postgress'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Habilita CORS
CORS(app)

# Registra endpoints sob /api
for bp in (user_bp, cliente_bp, visita_bp, campanha_bp, resgate_bp, dashboard_bp):
    app.register_blueprint(bp, url_prefix='/api')

# Inicializa o banco e cria tabelas, se necessário
db.init_app(app)
with app.app_context():
    db.create_all()

# Rota para servir o seu SPA (index.html + assets)
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder = app.static_folder
    target = os.path.join(static_folder, path)
    if path and os.path.exists(target):
        return send_from_directory(static_folder, path)
    index_file = os.path.join(static_folder, 'index.html')
    if os.path.exists(index_file):
        return send_from_directory(static_folder, 'index.html')
    return "index.html not found", 404

if __name__ == '__main__':
    # Lê host, porta e debug de variáveis de ambiente
    host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_RUN_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

    app.run(host=host, port=port, debug=debug)
