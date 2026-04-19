"""
Platform API Controller'ı (Blueprint)
"""
from flask import Blueprint, request, jsonify
from app.models.platform import PlatformModel
from app.models.configuration import ConfigurationModel
from app.models.requirement import RequirementModel
from app.utils.auth import login_required
from app.utils.database import mysql
from app.utils.logging import record_log, LogType

platform_api_bp = Blueprint('platform_api', __name__, url_prefix='/api')


# ── PLATFORM CRUD ──────────────────────────────────────────────────────────

@platform_api_bp.route('/platform', methods=['GET'])
@login_required
def get_platforms():
    """Tüm platformları döndür"""
    model = PlatformModel(mysql)
    platforms = model.get_all()
    return jsonify(platforms)


@platform_api_bp.route('/platform', methods=['POST'])
@login_required
def create_platform():
    """Yeni platform oluştur"""
    data = request.json
    
    if not data or 'PlatformAdi' not in data:
        return jsonify({'error': 'Platform adı gerekli'}), 400
    
    model = PlatformModel(mysql)
    new_id = model.create(data['PlatformAdi'])
    
    record_log('platform_list', new_id, 'Platform', '-', data['PlatformAdi'], LogType.CREATE.value)
    
    return jsonify({'PlatformID': new_id}), 201


@platform_api_bp.route('/platform/<int:platform_id>', methods=['PUT'])
@login_required
def update_platform(platform_id):
    """Platform güncelle"""
    data = request.json
    
    if not data or 'PlatformAdi' not in data:
        return jsonify({'error': 'Platform adı gerekli'}), 400
    
    model = PlatformModel(mysql)
    existing = model.get_by_id(platform_id)
    
    if not existing:
        return jsonify({'error': 'Platform bulunamadı'}), 404
    
    model.update(platform_id, data['PlatformAdi'])
    
    record_log('platform_list', platform_id, 'PlatformAdi', 
               existing['PlatformAdi'], data['PlatformAdi'], LogType.UPDATE.value)
    
    return jsonify({'ok': True})


@platform_api_bp.route('/platform/<int:platform_id>', methods=['DELETE'])
@login_required
def delete_platform(platform_id):
    """Platform sil"""
    model = PlatformModel(mysql)
    existing = model.get_by_id(platform_id)
    
    if not existing:
        return jsonify({'error': 'Platform bulunamadı'}), 404
    
    if existing.get('HavuzMu'):
        return jsonify({'error': 'Havuz platform silinemez'}), 400
    
    # İsterleri sil ve günlüğe kaydet
    req_model = RequirementModel(mysql)
    nodes = req_model.get_tree(platform_id)
    
    for node in nodes:
        record_log('ister_node', node['NodeID'], 'Node', node['Icerik'], '-', LogType.DELETE.value)
    
    model.delete(platform_id)
    record_log('platform_list', platform_id, 'Platform', existing['PlatformAdi'], '-', LogType.DELETE.value)
    
    return jsonify({'ok': True})


# ── PLATFORM KONFİGÜRASYON ────────────────────────────────────────────────

@platform_api_bp.route('/platform/<int:platform_id>/konfig', methods=['GET'])
@login_required
def get_platform_configs(platform_id):
    """Platform'un konfigürasyonlarını döndür"""
    model = ConfigurationModel(mysql)
    config_ids = model.get_by_platform(platform_id)
    return jsonify(config_ids)


@platform_api_bp.route('/platform/<int:platform_id>/konfig', methods=['POST'])
@login_required
def set_platform_configs(platform_id):
    """Platform'un konfigürasyonlarını ayarla"""
    data = request.json
    
    if not data or 'konfig_ids' not in data:
        return jsonify({'error': 'Konfigürasyon listesi gerekli'}), 400
    
    model = ConfigurationModel(mysql)
    model.set_platform_configs(platform_id, data['konfig_ids'])
    
    return jsonify({'ok': True})


# ── HATA #9 DÜZELTMESİ: Eksik endpoint eklendi ──────────────────────────────

@platform_api_bp.route('/platform/<int:pid>/ister_seti_olustur', methods=['POST'])
@login_required
def ister_seti_olustur(pid):
    """Havuzdan platforma ister seti kopyala"""
    import MySQLdb.cursors
    from flask import session as flask_session
    from app.utils.database import get_dict_cursor

    cur  = get_dict_cursor()
    cur2 = mysql.connection.cursor()

    # Havuz platformunu bul
    cur.execute("SELECT PlatformID FROM platform_list WHERE HavuzMu=1 LIMIT 1")
    havuz = cur.fetchone()
    if not havuz:
        cur.close()
        return jsonify({'hata': 'Havuz platformu bulunamadı.'}), 400
    havuz_pid = havuz['PlatformID']

    # Platformun seçili konfiglerini al
    cur.execute("SELECT KonfigID FROM platform_konfig WHERE PlatformID=%s", (pid,))
    konfig_ids = [r['KonfigID'] for r in cur.fetchall()]
    if not konfig_ids:
        cur.close()
        return jsonify({'hata': 'Platform için konfig seçilmemiş.'}), 400

    # Seviye eşleştirme
    cur.execute("SELECT * FROM seviye_tanim WHERE PlatformID=%s ORDER BY SeviyeNo", (pid,))
    seviyeler = cur.fetchall()
    if not seviyeler:
        cur.close()
        return jsonify({'hata': 'Platform için seviye tanımlanmamış.'}), 400

    cur.execute("SELECT * FROM seviye_tanim WHERE PlatformID=%s ORDER BY SeviyeNo", (havuz_pid,))
    havuz_seviyeler = cur.fetchall()
    havuz_sev_map = {s['SeviyeNo']: s['SeviyeID'] for s in havuz_seviyeler}
    plat_sev_map  = {s['SeviyeNo']: s['SeviyeID'] for s in seviyeler}

    # Mevcut node'ları ve TA dokümanlarını sil
    cur2.execute("DELETE FROM ister_node WHERE PlatformID=%s", (pid,))
    cur2.execute("DELETE FROM ta_dokuman WHERE PlatformID=%s", (pid,))
    mysql.connection.commit()

    # Havuzdan kopyala
    konfig_str = ','.join(str(k) for k in konfig_ids)
    cur.execute(f"""SELECT n.* FROM ister_node n
                   WHERE n.PlatformID=%s AND (n.KonfigID IN ({konfig_str}) OR n.KonfigID IS NULL)
                   ORDER BY n.NodeID""", (havuz_pid,))
    havuz_nodes = cur.fetchall()

    id_map = {}
    for hn in havuz_nodes:
        cur.execute("SELECT SeviyeNo FROM seviye_tanim WHERE SeviyeID=%s", (hn['SeviyeID'],))
        sev_row = cur.fetchone()
        if not sev_row or sev_row['SeviyeNo'] not in plat_sev_map:
            continue
        yeni_seviye_id = plat_sev_map[sev_row['SeviyeNo']]
        yeni_parent    = id_map.get(hn['ParentID']) if hn['ParentID'] else None

        cur2.execute("""INSERT INTO ister_node
                        (PlatformID, SeviyeID, ParentID, HavuzNodeID, KonfigID,
                         NodeNumarasi, Icerik, TestYontemiID, OlusturanID,HavuzKodu)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                     (pid, yeni_seviye_id, yeni_parent, hn['NodeID'], hn['KonfigID'],
                      hn.get('NodeNumarasi', ''), hn['Icerik'], hn['TestYontemiID'],
                      flask_session.get('kullanici_id'), hn.get('HavuzKodu', '')))
        mysql.connection.commit()
        id_map[hn['NodeID']] = cur2.lastrowid

    # TA dokümanlarını kopyala
    cur.execute("SELECT * FROM ta_dokuman WHERE PlatformID=%s", (havuz_pid,))
    ta_id_map = {}
    for ta in cur.fetchall():
        cur2.execute("""INSERT INTO ta_dokuman (PlatformID, SiraNo, HavuzTaID, SolSistemAdi, SagSistemAdi)
                        VALUES (%s,%s,%s,%s,%s)""",
                     (pid, ta['SiraNo'], ta['TaID'], ta['SolSistemAdi'], ta['SagSistemAdi']))
        mysql.connection.commit()
        ta_id_map[ta['TaID']] = cur2.lastrowid

        cur.execute("SELECT * FROM ta_veri WHERE TaID=%s", (ta['TaID'],))
        for v in cur.fetchall():
            cur2.execute("INSERT INTO ta_veri (TaID,Sistem,Yon,Icerik,Sira) VALUES (%s,%s,%s,%s,%s)",
                         (ta_id_map[ta['TaID']], v['Sistem'], v['Yon'], v['Icerik'], v['Sira']))

        cur.execute("SELECT * FROM ta_sgo_baglanti WHERE TaID=%s", (ta['TaID'],))
        for b in cur.fetchall():
            yeni_node = id_map.get(b['NodeID'])
            if yeni_node:
                cur2.execute("INSERT IGNORE INTO ta_sgo_baglanti (TaID,NodeID) VALUES (%s,%s)",
                             (ta_id_map[ta['TaID']], yeni_node))
        mysql.connection.commit()

    cur.close()
    cur2.close()
    return jsonify({'ok': True, 'mesaj': f'{len(id_map)} ister kopyalandı.'})
