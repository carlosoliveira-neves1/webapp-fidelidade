from flask import Blueprint, request, jsonify
from src.models.user import db, Cliente, Visita, Ponto, Resgate, Brinde, Campanha, StatusResgateEnum, NivelEnum
from datetime import datetime, timedelta
from sqlalchemy import func, desc

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard/resumo', methods=['GET'])
def resumo_dashboard():
    """Retorna resumo geral para o dashboard"""
    try:
        # Estatísticas gerais
        total_clientes = Cliente.query.count()
        total_visitas = Visita.query.count()
        total_resgates = Resgate.query.count()
        campanhas_ativas = Campanha.query.filter_by(ativa=True).count()
        
        # Estatísticas do mês atual
        inicio_mes = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        fim_mes = (inicio_mes + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        visitas_mes = Visita.query.filter(
            Visita.data_visita >= inicio_mes,
            Visita.data_visita <= fim_mes
        ).count()
        
        novos_clientes_mes = Cliente.query.filter(
            Cliente.data_cadastro >= inicio_mes,
            Cliente.data_cadastro <= fim_mes
        ).count()
        
        resgates_mes = Resgate.query.filter(
            Resgate.data_resgate >= inicio_mes,
            Resgate.data_resgate <= fim_mes
        ).count()
        
        # Valor total de compras do mês
        valor_total_mes = db.session.query(func.sum(Visita.valor_compra))\
                                   .filter(
                                       Visita.data_visita >= inicio_mes,
                                       Visita.data_visita <= fim_mes
                                   ).scalar() or 0
        
        return jsonify({
            'estatisticas_gerais': {
                'total_clientes': total_clientes,
                'total_visitas': total_visitas,
                'total_resgates': total_resgates,
                'campanhas_ativas': campanhas_ativas
            },
            'estatisticas_mes': {
                'visitas_mes': visitas_mes,
                'novos_clientes_mes': novos_clientes_mes,
                'resgates_mes': resgates_mes,
                'valor_total_mes': float(valor_total_mes)
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/dashboard/top-clientes', methods=['GET'])
def top_clientes():
    """Retorna top 10 clientes por diferentes critérios"""
    try:
        # Top 10 por pontuação
        top_pontos = db.session.query(Cliente, Ponto)\
                              .join(Ponto)\
                              .order_by(desc(Ponto.pontos_acumulados))\
                              .limit(10)\
                              .all()
        
        # Top 10 por número de visitas
        top_visitas = db.session.query(Cliente, func.count(Visita.id).label('total_visitas'))\
                               .join(Visita)\
                               .group_by(Cliente.id)\
                               .order_by(desc('total_visitas'))\
                               .limit(10)\
                               .all()
        
        # Top 10 por valor de compras
        top_valor = db.session.query(Cliente, func.sum(Visita.valor_compra).label('valor_total'))\
                             .join(Visita)\
                             .group_by(Cliente.id)\
                             .order_by(desc('valor_total'))\
                             .limit(10)\
                             .all()
        
        return jsonify({
            'top_pontos': [
                {
                    'cliente': cliente.to_dict(),
                    'pontos': ponto.pontos_acumulados,
                    'nivel': ponto.nivel_atual.value
                }
                for cliente, ponto in top_pontos
            ],
            'top_visitas': [
                {
                    'cliente': cliente.to_dict(),
                    'total_visitas': int(total_visitas)
                }
                for cliente, total_visitas in top_visitas
            ],
            'top_valor': [
                {
                    'cliente': cliente.to_dict(),
                    'valor_total': float(valor_total)
                }
                for cliente, valor_total in top_valor
            ]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/dashboard/visitas-periodo', methods=['GET'])
def visitas_por_periodo():
    """Retorna visitas agrupadas por período"""
    try:
        periodo = request.args.get('periodo', 'mes')  # mes, semana, dia
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        
        query = Visita.query
        
        if data_inicio:
            query = query.filter(Visita.data_visita >= datetime.fromisoformat(data_inicio))
        
        if data_fim:
            query = query.filter(Visita.data_visita <= datetime.fromisoformat(data_fim))
        
        if periodo == 'dia':
            # Agrupar por dia
            visitas_agrupadas = db.session.query(
                func.date(Visita.data_visita).label('periodo'),
                func.count(Visita.id).label('total_visitas'),
                func.sum(Visita.valor_compra).label('valor_total')
            ).group_by(func.date(Visita.data_visita))\
             .order_by('periodo')\
             .all()
        
        elif periodo == 'semana':
            # Agrupar por semana
            visitas_agrupadas = db.session.query(
                func.strftime('%Y-%W', Visita.data_visita).label('periodo'),
                func.count(Visita.id).label('total_visitas'),
                func.sum(Visita.valor_compra).label('valor_total')
            ).group_by(func.strftime('%Y-%W', Visita.data_visita))\
             .order_by('periodo')\
             .all()
        
        else:  # mes
            # Agrupar por mês
            visitas_agrupadas = db.session.query(
                func.strftime('%Y-%m', Visita.data_visita).label('periodo'),
                func.count(Visita.id).label('total_visitas'),
                func.sum(Visita.valor_compra).label('valor_total')
            ).group_by(func.strftime('%Y-%m', Visita.data_visita))\
             .order_by('periodo')\
             .all()
        
        return jsonify({
            'periodo': periodo,
            'dados': [
                {
                    'periodo': str(periodo),
                    'total_visitas': int(total_visitas),
                    'valor_total': float(valor_total or 0)
                }
                for periodo, total_visitas, valor_total in visitas_agrupadas
            ]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/dashboard/distribuicao-niveis', methods=['GET'])
def distribuicao_niveis():
    """Retorna distribuição de clientes por nível"""
    try:
        distribuicao = db.session.query(
            Ponto.nivel_atual,
            func.count(Ponto.id).label('total')
        ).group_by(Ponto.nivel_atual).all()
        
        return jsonify({
            'distribuicao': [
                {
                    'nivel': nivel.value,
                    'total': int(total)
                }
                for nivel, total in distribuicao
            ]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/dashboard/resgates-status', methods=['GET'])
def resgates_por_status():
    """Retorna resgates agrupados por status"""
    try:
        resgates_status = db.session.query(
            Resgate.status,
            func.count(Resgate.id).label('total')
        ).group_by(Resgate.status).all()
        
        return jsonify({
            'resgates_status': [
                {
                    'status': status.value,
                    'total': int(total)
                }
                for status, total in resgates_status
            ]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/relatorios/clientes-detalhado', methods=['GET'])
def relatorio_clientes_detalhado():
    """Relatório detalhado de clientes"""
    try:
        # Filtros
        nivel_filter = request.args.get('nivel')
        data_cadastro_inicio = request.args.get('data_cadastro_inicio')
        data_cadastro_fim = request.args.get('data_cadastro_fim')
        min_visitas = request.args.get('min_visitas', type=int)
        min_pontos = request.args.get('min_pontos', type=int)
        
        # Query base com joins
        query = db.session.query(Cliente, Ponto)\
                         .outerjoin(Ponto)\
                         .outerjoin(Visita)
        
        if nivel_filter:
            try:
                nivel_enum = NivelEnum(nivel_filter)
                query = query.filter(Ponto.nivel_atual == nivel_enum)
            except ValueError:
                return jsonify({'error': 'Nível inválido'}), 400
        
        if data_cadastro_inicio:
            query = query.filter(Cliente.data_cadastro >= datetime.fromisoformat(data_cadastro_inicio))
        
        if data_cadastro_fim:
            query = query.filter(Cliente.data_cadastro <= datetime.fromisoformat(data_cadastro_fim))
        
        clientes_pontos = query.all()
        
        # Processar dados
        relatorio = []
        for cliente, ponto in clientes_pontos:
            # Calcular estatísticas do cliente
            total_visitas = len(cliente.visitas)
            valor_total_compras = sum([v.valor_compra for v in cliente.visitas])
            pontos_totais = ponto.pontos_acumulados if ponto else 0
            
            # Aplicar filtros adicionais
            if min_visitas and total_visitas < min_visitas:
                continue
            if min_pontos and pontos_totais < min_pontos:
                continue
            
            # Última visita
            ultima_visita = None
            if cliente.visitas:
                ultima_visita = max(cliente.visitas, key=lambda v: v.data_visita)
            
            # Resgates do cliente
            resgates_pendentes = len([r for r in cliente.resgates if r.status == StatusResgateEnum.PENDENTE])
            resgates_entregues = len([r for r in cliente.resgates if r.status == StatusResgateEnum.ENTREGUE])
            
            relatorio.append({
                'cliente': cliente.to_dict(),
                'pontos': {
                    'total': pontos_totais,
                    'nivel': ponto.nivel_atual.value if ponto else 'Bronze'
                },
                'estatisticas': {
                    'total_visitas': total_visitas,
                    'valor_total_compras': valor_total_compras,
                    'valor_medio_compra': valor_total_compras / total_visitas if total_visitas > 0 else 0,
                    'ultima_visita': ultima_visita.data_visita.isoformat() if ultima_visita else None,
                    'resgates_pendentes': resgates_pendentes,
                    'resgates_entregues': resgates_entregues
                }
            })
        
        return jsonify({
            'relatorio': relatorio,
            'total_clientes': len(relatorio)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/relatorios/campanhas-performance', methods=['GET'])
def relatorio_campanhas_performance():
    """Relatório de performance das campanhas"""
    try:
        campanhas = Campanha.query.all()
        
        relatorio_campanhas = []
        
        for campanha in campanhas:
            # Estatísticas da campanha
            total_brindes = len(campanha.brindes)
            brindes_disponiveis = sum([b.quantidade_disponivel for b in campanha.brindes])
            
            # Resgates da campanha
            resgates_campanha = db.session.query(Resgate)\
                                         .join(Brinde)\
                                         .filter(Brinde.campanha_id == campanha.id)\
                                         .all()
            
            total_resgates = len(resgates_campanha)
            resgates_entregues = len([r for r in resgates_campanha if r.status == StatusResgateEnum.ENTREGUE])
            resgates_pendentes = len([r for r in resgates_campanha if r.status == StatusResgateEnum.PENDENTE])
            
            # Visitas no período da campanha
            visitas_periodo = Visita.query.filter(
                Visita.data_visita >= campanha.data_inicio,
                Visita.data_visita <= campanha.data_fim
            )
            
            if campanha.loja:
                visitas_periodo = visitas_periodo.filter(Visita.loja == campanha.loja)
            
            visitas_periodo = visitas_periodo.all()
            total_visitas_periodo = len(visitas_periodo)
            valor_total_periodo = sum([v.valor_compra for v in visitas_periodo])
            
            relatorio_campanhas.append({
                'campanha': campanha.to_dict(),
                'brindes': {
                    'total_tipos': total_brindes,
                    'total_disponivel': brindes_disponiveis
                },
                'resgates': {
                    'total': total_resgates,
                    'entregues': resgates_entregues,
                    'pendentes': resgates_pendentes,
                    'taxa_entrega': (resgates_entregues / total_resgates * 100) if total_resgates > 0 else 0
                },
                'visitas_periodo': {
                    'total': total_visitas_periodo,
                    'valor_total': valor_total_periodo
                }
            })
        
        return jsonify({
            'campanhas': relatorio_campanhas
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

