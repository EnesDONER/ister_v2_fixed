"""
İster Node (Gereksinim) API Controller'ı (Blueprint)
"""
from flask import Blueprint, request, jsonify, session
import MySQLdb.cursors
from app.models.requirement import RequirementModel
from app.utils.auth import login_required
from app.utils.database import mysql, get_dict_cursor
from app.utils.logging import record_log, LogType

requirement_api_bp = Blueprint('requirement_api', __name__, url_prefix='/api')


# ── İSTER AĞACI ───────────────────────────────────────────────────────────────

@requirement_api_bp.route('/platform/<int:platform_id>/ister_agaci', methods=['GET'])
@login_required
def get_requirement_tree(platform_id):
    """Platform için ister ağacını döndür"""
    num_filter = request.args.get('numara', '').strip()
    model = RequirementModel(mysql)
    return jsonify(model.get_tree(platform_id, num_filter))


# ── CRUD ──────────────────────────────────────────────────────────────────────

@requirement_api_bp.route('/ister_node', methods=['POST'])
@login_required
def create_requirement():
    data = request.json
    for field in ['PlatformID', 'SeviyeID']:
        if field not in data:
            return jsonify({'error': f'{field} gerekli'}), 400

    model = RequirementModel(mysql)
    new_id = model.create(
        platform_id=data['PlatformID'],
        level_id=data['SeviyeID'],
        content=data.get('Icerik', ''),
        ParentID=data.get('ParentID'),
        KonfigID=data.get('KonfigID'),
        NodeNumarasi=data.get('NodeNumarasi', ''),
        IsterTipi=data.get('IsterTipi', 'G'),
        HavuzKodu=data.get('HavuzKodu', ''),
        TestYontemiID=data.get('TestYontemiID'),
        IlgiliAsamaID=data.get('IlgiliAsamaID'),
        OlusturanID=session.get('kullanici_id')
    )
    record_log('ister_node', new_id, 'Node', '-', data.get('Icerik', ''), LogType.CREATE.value)

    nodes = RequirementModel(mysql).get_tree(data['PlatformID'])
    new_node = next((n for n in nodes if n['NodeID'] == new_id), {})
    return jsonify({'NodeID': new_id, 'HavuzKodu': new_node.get('HavuzKodu', '')}), 201


# @requirement_api_bp.route('/ister_node/<int:node_id>', methods=['PUT'])
# @login_required
# def update_requirement(node_id):
#     data = request.json
#     model = RequirementModel(mysql)
#     print(f"Updating NodeID {node_id} with data: {data}")  # Debug log
#     cur = model.get_dict_cursor()
#     cur.execute("SELECT * FROM ister_node WHERE NodeID=%s", (node_id,))
#     old_node = cur.fetchone()
#     cur.close()

#     if not old_node:
#         return jsonify({'error': 'İster bulunamadı'}), 404

#     field_map = ['Icerik', 'TestYontemiID', 'NodeNumarasi', 'IsterTipi',
#                  'HavuzKodu', 'KonfigID', 'SeviyeID', 'ParentID']
#     updates = {f: data[f] for f in field_map if f in data}

#     if updates:
#         model.update(node_id, old_platform_id=old_node.get('PlatformID'), **updates)
#         for field, new_val in updates.items():
#             old_val = old_node.get(field)
#             if str(old_val or '') != str(new_val or ''):
#                 record_log('ister_node', node_id, field, old_val, new_val, LogType.UPDATE.value)

#     return jsonify({'ok': True})

@requirement_api_bp.route('/ister_node/<int:node_id>', methods=['PUT'])
@login_required
def update_requirement(node_id):
    data = request.json
    model = RequirementModel(mysql)
    cur = model.get_dict_cursor()
    cur.execute("SELECT * FROM ister_node WHERE NodeID=%s", (node_id,))
    old_node = cur.fetchone()

    if not old_node:
        cur.close()
        return jsonify({'error': 'İster bulunamadı'}), 404

    field_map = ['Icerik', 'TestYontemiID', 'NodeNumarasi', 'IsterTipi',
                 'HavuzKodu', 'KonfigID', 'SeviyeID', 'ParentID']
    updates = {f: data[f] for f in field_map if f in data}

    # HavuzKodu güncelleme: ilgili tüm node'lara yay
    new_havuz_kodu = updates.get('HavuzKodu')
    if new_havuz_kodu is not None and str(new_havuz_kodu).strip() != '':
        havuz_node_id = old_node.get('HavuzNodeID')

        if havuz_node_id:
            # 1) HavuzNodeID = NodeID olan node'u güncelle (havuz ana node'u)
            cur.execute(
                "UPDATE ister_node SET HavuzKodu=%s WHERE NodeID=%s",
                (new_havuz_kodu, havuz_node_id)
            )
            # Ana node için log
            cur.execute("SELECT HavuzKodu FROM ister_node WHERE NodeID=%s", (havuz_node_id,))
            ana_node = cur.fetchone()
            if ana_node and str(ana_node.get('HavuzKodu') or '') != str(new_havuz_kodu):
                record_log('ister_node', havuz_node_id, 'HavuzKodu',
                           ana_node.get('HavuzKodu'), new_havuz_kodu, LogType.UPDATE.value)

            # 2) Aynı HavuzNodeID'ye sahip tüm node'ları güncelle (mevcut node dahil)
            cur.execute(
                "UPDATE ister_node SET HavuzKodu=%s WHERE HavuzNodeID=%s",
                (new_havuz_kodu, havuz_node_id)
            )
            # Etkilenen kardeş node'lar için log
            cur.execute(
                "SELECT NodeID, HavuzKodu FROM ister_node WHERE HavuzNodeID=%s",
                (havuz_node_id,)
            )
            siblings = cur.fetchall()
            for sibling in siblings:
                if str(sibling.get('HavuzKodu') or '') != str(new_havuz_kodu):
                    record_log('ister_node', sibling['NodeID'], 'HavuzKodu',
                               sibling.get('HavuzKodu'), new_havuz_kodu, LogType.UPDATE.value)

        # updates içindeki HavuzKodu zaten ana update'de işlenecek,
        # tekrar işlenmemesi için çıkar
        updates.pop('HavuzKodu', None)

    cur.close()

    if updates:
        model.update(node_id, old_platform_id=old_node.get('PlatformID'), **updates)
        for field, new_val in updates.items():
            old_val = old_node.get(field)
            if str(old_val or '') != str(new_val or ''):
                record_log('ister_node', node_id, field, old_val, new_val, LogType.UPDATE.value)

    return jsonify({'ok': True})

@requirement_api_bp.route('/ister_node/<int:node_id>', methods=['DELETE'])
@login_required
def delete_requirement(node_id):
    model = RequirementModel(mysql)

    cur = model.get_dict_cursor()
    cur.execute("""SELECT n.PlatformID, n.Icerik, p.HavuzMu
                   FROM ister_node n
                   JOIN platform_list p ON n.PlatformID=p.PlatformID
                   WHERE n.NodeID=%s""", (node_id,))
    node = cur.fetchone()
    cur.close()

    if not node:
        return jsonify({'error': 'İster bulunamadı'}), 404

    record_log('ister_node', node_id, 'Node', node['Icerik'], '-', LogType.DELETE.value)
    platform_id = node['PlatformID']
    havuz_mu    = node.get('HavuzMu', 0)

    model.delete(node_id)

    # HATA #6 DÜZELTMESİ: Havuz platformunda silme sonrası kodları yeniden sırala
    if havuz_mu:
        _renumber_pool_codes(platform_id)

    return jsonify({'ok': True})


@requirement_api_bp.route('/ister_node/siralama', methods=['POST'])
@login_required
def reorder_requirement():
    data = request.json
    if not data or 'NodeID' not in data or 'Yon' not in data:
        return jsonify({'error': 'NodeID ve Yon gerekli'}), 400
    RequirementModel(mysql).reorder(data['NodeID'], data['Yon'])
    return jsonify({'ok': True})


# ── HATA #12 DÜZELTMESİ: ORDER BY düzeltildi ─────────────────────────────────

@requirement_api_bp.route('/tum_isterler', methods=['GET'])
@login_required
def get_all_requirements():
    """Tüm platformların isterlerini döndür"""
    platform_id = request.args.get('platform_id')
    havuz_kodu  = request.args.get('havuz_kodu')

    cur = get_dict_cursor()
    q = """
    SELECT n.NodeID, n.PlatformID, n.ParentID, n.NodeNumarasi,
           n.IsterTipi, n.HavuzKodu, n.Icerik, n.DegistirildiMi,
           COALESCE(n.SiraNo, n.NodeID) AS SiraNo,
           p.PlatformAdi, p.HavuzMu,
           s.SeviyeAdi, s.SeviyeNo, k.KonfigAdi
    FROM ister_node n
    JOIN platform_list p ON n.PlatformID=p.PlatformID
    JOIN seviye_tanim s ON n.SeviyeID=s.SeviyeID
    LEFT JOIN konfig_list k ON n.KonfigID=k.KonfigID
    WHERE p.HavuzMu=0
    """
    params = []
    if platform_id:
        q += " AND n.PlatformID=%s"
        params.append(platform_id)
    if havuz_kodu:
        q += " AND n.HavuzKodu=%s"
        params.append(havuz_kodu)

    # HATA #12 DÜZELTMESİ: ParentID IS NULL DESC eklendi
    q += " ORDER BY p.PlatformAdi, n.ParentID IS NULL DESC, n.SiraNo, n.NodeID"

    cur.execute(q, params)
    data = cur.fetchall()
    cur.close()
    return jsonify(data)


# ── HATA #10 DÜZELTMESİ: Eksik endpoint eklendi ─────────────────────────────

@requirement_api_bp.route('/gign/sonraki_numara', methods=['GET'])
@login_required
def gign_sonraki_numara():
    """Otomatik numara üret"""
    parent_id   = request.args.get('parent_id')
    platform_id = request.args.get('platform_id')
    cur = get_dict_cursor()

    if parent_id:
        cur.execute("SELECT NodeNumarasi FROM ister_node WHERE NodeID=%s", (parent_id,))
        parent = cur.fetchone()
        parent_num = (parent['NodeNumarasi'] or '') if parent else ''

        cur.execute("""SELECT NodeNumarasi FROM ister_node
                       WHERE ParentID=%s AND NodeNumarasi IS NOT NULL AND NodeNumarasi!=''
                       ORDER BY LENGTH(NodeNumarasi) DESC, NodeNumarasi DESC LIMIT 1""", (parent_id,))
        son = cur.fetchone()
        if son and son['NodeNumarasi']:
            sn = son['NodeNumarasi']
            try:
                if '-' in sn:
                    bas, sayi = sn.rsplit('-', 1)
                    yeni = f"{bas}-{int(sayi)+1}"
                elif parent_num:
                    yeni = f"{parent_num}-1"
                else:
                    yeni = f"{sn}-1"
            except:
                yeni = f"{parent_num}-1" if parent_num else ''
        else:
            yeni = f"{parent_num}-1" if parent_num else ''
    else:
        cur.execute("""SELECT NodeNumarasi FROM ister_node
                       WHERE PlatformID=%s AND ParentID IS NULL
                       AND NodeNumarasi IS NOT NULL AND NodeNumarasi!=''
                       ORDER BY NodeNumarasi DESC LIMIT 1""", (platform_id,))
        son = cur.fetchone()
        if son and son['NodeNumarasi']:
            try:
                yeni = str(int(son['NodeNumarasi']) + 100)
            except:
                yeni = ''
        else:
            yeni = '4100'

    cur.close()
    return jsonify({'numara': yeni})


# ── HATA #11 DÜZELTMESİ: Eksik endpoint eklendi ─────────────────────────────

@requirement_api_bp.route('/toplu_upload', methods=['POST'])
@login_required
def toplu_upload():
    """Toplu ister yükleme"""
    d          = request.json
    pid        = d.get('platform_id')
    seviye_id  = d.get('seviye_id')
    parent_id  = d.get('parent_id')
    konfig_id  = d.get('konfig_id')
    ister_tipi = d.get('ister_tipi', 'G')
    isterler   = d.get('isterler', [])

    if not isterler or not pid or not seviye_id:
        return jsonify({'hata': 'Eksik parametre'}), 400

    cur  = get_dict_cursor()
    cur2 = mysql.connection.cursor()

    cur.execute("SELECT HavuzMu FROM platform_list WHERE PlatformID=%s", (pid,))
    p = cur.fetchone()
    is_havuz = p and p.get('HavuzMu')

    # Başlangıç numarası
    if parent_id:
        cur.execute("SELECT NodeNumarasi FROM ister_node WHERE NodeID=%s", (parent_id,))
        pn = cur.fetchone()
        parent_num = pn['NodeNumarasi'] if pn and pn['NodeNumarasi'] else ''
        cur.execute("""SELECT NodeNumarasi FROM ister_node WHERE ParentID=%s
                       AND NodeNumarasi IS NOT NULL ORDER BY NodeNumarasi DESC LIMIT 1""", (parent_id,))
    else:
        parent_num = ''
        cur.execute("""SELECT NodeNumarasi FROM ister_node WHERE PlatformID=%s AND ParentID IS NULL
                       AND NodeNumarasi IS NOT NULL ORDER BY NodeNumarasi DESC LIMIT 1""", (pid,))

    son = cur.fetchone()
    if son and son['NodeNumarasi']:
        try:
            parts = son['NodeNumarasi'].rsplit('.', 1)
            son_sayi = int(parts[1]) if len(parts) == 2 else int(son['NodeNumarasi'])
            prefix   = parts[0] + '.' if len(parts) == 2 else ''
        except:
            son_sayi = 0
            prefix   = parent_num + '.' if parent_num else ''
    else:
        son_sayi = 0
        prefix   = parent_num + '.' if parent_num else ''

    # Havuz kodu sayacı — HATA #8 mantığıyla MAX kullan
    prefix_kod = 'b' if ister_tipi == 'B' else 'g'
    cur.execute("""SELECT COALESCE(MAX(CAST(SUBSTRING(HavuzKodu,2) AS UNSIGNED)),0) AS mx
                   FROM ister_node WHERE PlatformID=%s AND IsterTipi=%s
                   AND HavuzKodu REGEXP %s""",
                (pid, ister_tipi, f'^{prefix_kod}[0-9]+$'))
    mx_row  = cur.fetchone()
    kod_say = mx_row['mx'] if mx_row else 0

    eklenenler = []
    for i, icerik in enumerate(isterler):
        icerik = str(icerik).strip()
        if not icerik:
            continue
        son_sayi   += 1
        numara      = f"{prefix}{son_sayi}"
        havuz_kodu  = f"{prefix_kod}{kod_say + i + 1}" if is_havuz else ''

        cur2.execute("""INSERT INTO ister_node
                        (PlatformID, SeviyeID, ParentID, KonfigID, NodeNumarasi,
                         IsterTipi, HavuzKodu, Icerik, OlusturanID)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                     (pid, seviye_id, parent_id, konfig_id, numara,
                      ister_tipi, havuz_kodu, icerik, session.get('kullanici_id')))
        mysql.connection.commit()
        eklenenler.append({'NodeID': cur2.lastrowid, 'NodeNumarasi': numara, 'Icerik': icerik})

    cur.close()
    cur2.close()
    return jsonify({'ok': True, 'toplam': len(eklenenler)})


# ── YARDIMCI: Havuz kodu yeniden sıralama (Hata #6) ─────────────────────────

def _renumber_pool_codes(platform_id):
    """Havuz platformunda silme sonrası g/b kodlarını ve alt numara sırasını yenile"""
    cur  = get_dict_cursor()
    cur2 = mysql.connection.cursor()

    cur.execute("""SELECT NodeID, IsterTipi, HavuzKodu, NodeNumarasi, ParentID,
                          COALESCE(SiraNo, NodeID) AS SiraNo
                   FROM ister_node WHERE PlatformID=%s
                   ORDER BY COALESCE(SiraNo, NodeID)""", (platform_id,))
    nodes = cur.fetchall()

    # HavuzKodu yeniden numaralandır
    g_say = 0
    b_say = 0
    for n in nodes:
        eski = n['HavuzKodu'] or ''
        if n['IsterTipi'] == 'G' and eski.startswith('g'):
            g_say += 1
            yeni = f"g{g_say}"
            if yeni != eski:
                cur2.execute("UPDATE ister_node SET HavuzKodu=%s WHERE NodeID=%s", (yeni, n['NodeID']))
        elif n['IsterTipi'] == 'B' and eski.startswith('b'):
            b_say += 1
            yeni = f"b{b_say}"
            if yeni != eski:
                cur2.execute("UPDATE ister_node SET HavuzKodu=%s WHERE NodeID=%s", (yeni, n['NodeID']))

    # NodeNumarasi yeniden numaralandır (alt seviyeler)
    def renumber_children(parent_id, parent_num):
        children = sorted(
            [n for n in nodes if n.get('ParentID') == parent_id],
            key=lambda x: x['SiraNo']
        )
        for i, c in enumerate(children, 1):
            eski = c['NodeNumarasi'] or ''
            yeni = f"{parent_num}-{i}" if parent_num else eski
            if yeni and yeni != eski:
                cur2.execute("UPDATE ister_node SET NodeNumarasi=%s WHERE NodeID=%s", (yeni, c['NodeID']))
                c['NodeNumarasi'] = yeni
            renumber_children(c['NodeID'], yeni)

    roots = [n for n in nodes if not n.get('ParentID')]
    for root in roots:
        renumber_children(root['NodeID'], root['NodeNumarasi'] or '')

    mysql.connection.commit()
    cur.close()
    cur2.close()
