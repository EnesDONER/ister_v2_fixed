"""
Pano (Dashboard) ve Rapor API Controller'ı (Blueprint)
"""
from flask import Blueprint, jsonify, request
from app.models.dashboard import DashboardModel
from app.models.platform import PlatformModel
from app.models.requirement import RequirementModel
from app.utils.auth import login_required
from app.utils.database import mysql, get_dict_cursor

dashboard_api_bp = Blueprint('dashboard_api', __name__, url_prefix='/api')


@dashboard_api_bp.route('/dashboard', methods=['GET'])
@login_required
def get_dashboard():
    """Dashboard özet verilerini döndür"""
    model = DashboardModel(mysql)
    platformlar = model.get_summary()

    # get_summary() düz liste dönüyor — JS'in beklediği obje formatına wrap et
    if isinstance(platformlar, list):
        plat_say   = len(platformlar)
        tgd_toplam = sum(p.get('TGDSayi', 0) for p in platformlar)
        bas_toplam = sum(p.get('BasariliTest', 0) for p in platformlar)
        hat_toplam = sum(p.get('HataliTest', 0) for p in platformlar)
        top_test   = sum(p.get('ToplamTest', 0) for p in platformlar)
        basari_orani = round(bas_toplam / top_test * 100) if top_test else 0

        return jsonify({
            'platform_sayisi': plat_say,
            'tgd_toplam':      tgd_toplam,
            'basari_orani':    basari_orani,
            'hatali_test':     hat_toplam,
            'platformlar':     platformlar,
        })

    # Zaten obje dönüyorsa olduğu gibi geç
    return jsonify(platformlar)


@dashboard_api_bp.route('/export/dashboard', methods=['GET'])
@login_required
def export_dashboard():
    """Dashboard verilerini export için döndür (dashboard ile aynı format)"""
    model = DashboardModel(mysql)
    platformlar = model.get_summary()

    if isinstance(platformlar, list):
        plat_say   = len(platformlar)
        tgd_toplam = sum(p.get('TGDSayi', 0) for p in platformlar)
        bas_toplam = sum(p.get('BasariliTest', 0) for p in platformlar)
        hat_toplam = sum(p.get('HataliTest', 0) for p in platformlar)
        top_test   = sum(p.get('ToplamTest', 0) for p in platformlar)
        basari_orani = round(bas_toplam / top_test * 100) if top_test else 0

        return jsonify({
            'platform_sayisi': plat_say,
            'tgd_toplam':      tgd_toplam,
            'basari_orani':    basari_orani,
            'hatali_test':     hat_toplam,
            'platformlar':     platformlar,
        })

    return jsonify(platformlar)


@dashboard_api_bp.route('/platform/<int:platform_id>/traceability', methods=['GET'])
@login_required
def get_traceability(platform_id):
    model = DashboardModel(mysql)
    return jsonify(model.get_platform_traceability(platform_id))


@dashboard_api_bp.route('/rapor/karsilastirma', methods=['GET'])
@login_required
def get_comparison_report():
    """Havuz isterlerini tüm platformlardaki karşılıklarıyla döndür"""
    platform_model    = PlatformModel(mysql)
    requirement_model = RequirementModel(mysql)

    pool_platform = platform_model.get_pool_platform()
    if not pool_platform:
        return jsonify({'error': 'Havuz platformu bulunamadı'}), 404

    all_platforms      = platform_model.get_all()
    non_pool_platforms = [p for p in all_platforms if not p.get('HavuzMu')]

    pool_requirements = requirement_model.get_tree(pool_platform['PlatformID'])

    def build_ordered(parent_id=None):
        children = sorted(
            [n for n in pool_requirements if n.get('ParentID') == parent_id],
            key=lambda x: (x.get('SiraNo') or x['NodeID'])
        )
        result = []
        for child in children:
            result.append(child)
            result.extend(build_ordered(child['NodeID']))
        return result

    ordered_pool = build_ordered(None)

    platform_map = {}
    for platform in non_pool_platforms:
        platform_reqs = requirement_model.get_tree(platform['PlatformID'])
        pid_str = str(platform['PlatformID'])
        for req in platform_reqs:
            code = req.get('HavuzKodu')
            if code and req.get('IsterTipi') != 'B':
                if code not in platform_map:
                    platform_map[code] = {}
                platform_map[code][pid_str] = {
                    'NodeNumarasi':   req.get('NodeNumarasi'),
                    'Icerik':         req.get('Icerik'),
                    'DegistirildiMi': req.get('DegistirildiMi')
                }

    return jsonify({
        'platformlar':    non_pool_platforms,
        'havuz_isterler': ordered_pool,
        'plat_map':       platform_map
    })


@dashboard_api_bp.route('/rapor/firma_gorusleri', methods=['GET'])
@login_required
def get_company_reviews():
    platform_id = request.args.get('platform_id')
    cur = get_dict_cursor()

    query = """SELECT g.GorusID, g.FirmaAdi, g.GorusKategori, g.GorusOzet,
                      g.OlusturmaTarihi, g.PlatformID, n.Icerik AS NodeIcerik,
                      n.NodeNumarasi, n.HavuzKodu, p.PlatformAdi,
                      s.SeviyeAdi, s.SeviyeNo
               FROM firma_gorusu g
               JOIN ister_node n ON g.NodeID=n.NodeID
               JOIN platform_list p ON g.PlatformID=p.PlatformID
               JOIN seviye_tanim s ON n.SeviyeID=s.SeviyeID"""

    params = []
    if platform_id:
        query += " WHERE g.PlatformID=%s"
        params.append(platform_id)
    query += " ORDER BY g.OlusturmaTarihi DESC"

    cur.execute(query, params)
    data = cur.fetchall()
    for row in data:
        if row.get('OlusturmaTarihi'):
            row['OlusturmaTarihi'] = row['OlusturmaTarihi'].strftime('%d.%m.%Y %H:%M')
    cur.close()
    return jsonify(data)


@dashboard_api_bp.route('/rapor/onay_durumu', methods=['GET'])
@login_required
def get_approval_status():
    platform_id = request.args.get('platform_id')
    cur = get_dict_cursor()

    query = """SELECT n.NodeID, n.Icerik, n.NodeNumarasi, n.IsterTipi, n.HavuzKodu,
                      s.SeviyeAdi, s.SeviyeNo, k.KonfigAdi, p.PlatformAdi, p.PlatformID,
                      COALESCE(o.OnayDurumu, 0) AS OnayDurumu,
                      COUNT(DISTINCT g.GorusID) AS GorusSayisi
               FROM ister_node n
               JOIN seviye_tanim s ON n.SeviyeID=s.SeviyeID
               JOIN platform_list p ON n.PlatformID=p.PlatformID
               LEFT JOIN konfig_list k ON n.KonfigID=k.KonfigID
               LEFT JOIN ister_onay o ON n.NodeID=o.NodeID AND o.PlatformID=n.PlatformID
               LEFT JOIN firma_gorusu g ON n.NodeID=g.NodeID AND g.PlatformID=n.PlatformID
               WHERE p.HavuzMu=0"""

    params = []
    if platform_id:
        query += " AND n.PlatformID=%s"
        params.append(platform_id)

    query += " GROUP BY n.NodeID, o.OnayDurumu ORDER BY p.PlatformAdi, s.SeviyeNo, n.NodeID"

    cur.execute(query, params)
    data = cur.fetchall()
    cur.close()
    return jsonify(data)