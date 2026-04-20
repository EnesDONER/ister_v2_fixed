"""
Firma Görüşü API Controller'ı (Blueprint)
firma_gorusu + firma_gorusu_yanit tabloları CRUD işlemleri
"""

from flask import Blueprint, jsonify, request, session
from app.utils.database import mysql
from app.utils.auth import login_required
from app.utils.logging import record_log, LogType

firma_gorusu_api_bp = Blueprint('firma_gorusu_api', __name__, url_prefix='/api')

# ── YARDIMCI ──────────────────────────────────────────────────────────────────

def _dict_cur():
    import MySQLdb.cursors
    return mysql.connection.cursor(MySQLdb.cursors.DictCursor)

# ── FİRMA GÖRÜŞÜ ──────────────────────────────────────────────────────────────

@firma_gorusu_api_bp.route('/firma_gorusu/<int:node_id>', methods=['GET'])
@login_required
def firma_gorusu_listesi(node_id):
    """
    Belirli bir node'a ait firma görüşlerini yanıtlarıyla birlikte döner.
    Query param: platform_id (opsiyonel)
    """
    pid = request.args.get('platform_id')
    cur = _dict_cur()

    q = """SELECT g.*, k.AdSoyad AS OlusturanAdi
           FROM firma_gorusu g
           LEFT JOIN kullanici k ON g.OlusturanID = k.KullaniciID
           WHERE g.NodeID = %s"""
    params = [node_id]

    if pid:
        q += " AND g.PlatformID = %s"
        params.append(pid)
    q += " ORDER BY g.OlusturmaTarihi"

    cur.execute(q, params)
    gorus_list = cur.fetchall()

    for g in gorus_list:
        if g.get('OlusturmaTarihi'):
            g['OlusturmaTarihi'] = g['OlusturmaTarihi'].strftime('%d.%m.%Y %H:%M')

        cur.execute(
            """SELECT y.*, k.AdSoyad AS YazanAdi
               FROM firma_gorusu_yanit y
               LEFT JOIN kullanici k ON y.YazanID = k.KullaniciID
               WHERE y.GorusID = %s
               ORDER BY y.OlusturmaTarihi""",
            (g['GorusID'],)
        )
        yanitlar = cur.fetchall()
        for y in yanitlar:
            if y.get('OlusturmaTarihi'):
                y['OlusturmaTarihi'] = y['OlusturmaTarihi'].strftime('%d.%m.%Y %H:%M')
        g['yanitlar'] = yanitlar

    cur.close()
    return jsonify(gorus_list)


@firma_gorusu_api_bp.route('/firma_gorusu', methods=['POST'])
@login_required
def firma_gorusu_ekle():
    """
    Yeni firma görüşü ekler.
    Body: { NodeID, PlatformID, FirmaAdi, GorusIcerik, GorusOzet, GorusKategori }
    """
    d = request.json
    cur = mysql.connection.cursor()
    cur.execute(
        """INSERT INTO firma_gorusu
               (NodeID, PlatformID, FirmaAdi, GorusIcerik, GorusOzet, GorusKategori, OlusturanID)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (
            d['NodeID'], d['PlatformID'], d['FirmaAdi'],
            d.get('GorusIcerik', ''), d.get('GorusOzet', ''),
            d.get('GorusKategori', ''), session['kullanici_id'],
        )
    )
    mysql.connection.commit()
    nid = cur.lastrowid
    cur.close()
    record_log('firma_gorusu', nid, 'Firma Görüşleri', '-', d['FirmaAdi'], LogType.CREATE.value)
    return jsonify({'GorusID': nid})


@firma_gorusu_api_bp.route('/firma_gorusu/<int:gid>', methods=['PUT'])
@login_required
def firma_gorusu_guncelle(gid):
    """
    Firma görüşünü günceller.
    Body: { FirmaAdi, GorusIcerik, GorusOzet, GorusKategori }
    """
    d = request.json
    cur = _dict_cur()
    cur.execute("SELECT FirmaAdi, GorusIcerik FROM firma_gorusu WHERE GorusID = %s", (gid,))
    row = cur.fetchone()
    if not row:
        cur.close()
        return jsonify({'ok': False, 'hata': 'Kayıt bulunamadı.'}), 404

    eski_firma_adi   = row['FirmaAdi']
    eski_gorus_icerik = row['GorusIcerik']
    yeni_firma_adi   = d.get('FirmaAdi',    eski_firma_adi)
    gorus_icerik     = d.get('GorusIcerik', eski_gorus_icerik)
    gorus_ozet       = d.get('GorusOzet',    None)
    gorus_kategori   = d.get('GorusKategori', None)

    cur.execute(
        "UPDATE firma_gorusu SET FirmaAdi=%s, GorusIcerik=%s, GorusOzet=%s, GorusKategori=%s WHERE GorusID=%s",
        (yeni_firma_adi, gorus_icerik, gorus_ozet, gorus_kategori, gid)
    )
    mysql.connection.commit()
    cur.close()
    record_log('firma_gorusu', gid, 'Firma Görüşleri', eski_firma_adi, yeni_firma_adi, LogType.UPDATE.value)
    return jsonify({'ok': True})


@firma_gorusu_api_bp.route('/firma_gorusu/<int:gid>', methods=['DELETE'])
@login_required
def firma_gorusu_sil(gid):
    """Firma görüşünü ve bağlı tüm yanıtları siler."""
    cur = _dict_cur()
    cur.execute("SELECT FirmaAdi FROM firma_gorusu WHERE GorusID = %s", (gid,))
    row = cur.fetchone()
    if not row:
        cur.close()
        return jsonify({'hata': 'Görüş bulunamadı.'}), 404

    firma_adi = row['FirmaAdi']
    # Bağlı yanıtlar cascade ile silinmiyorsa manuel sil
    cur.execute("DELETE FROM firma_gorusu_yanit WHERE GorusID = %s", (gid,))
    cur.execute("DELETE FROM firma_gorusu WHERE GorusID = %s", (gid,))
    mysql.connection.commit()
    cur.close()
    record_log('firma_gorusu', gid, 'Firma Görüşleri', firma_adi, '-', LogType.DELETE.value)
    return jsonify({'ok': True})


# ── FİRMA GÖRÜŞÜ YANITLARI ────────────────────────────────────────────────────

@firma_gorusu_api_bp.route('/firma_gorusu/<int:gid>/yanit', methods=['POST'])
@login_required
def firma_gorusu_yanit_ekle(gid):
    """
    Görüşe yanıt ekler.
    Body: { YanitIcerik }
    """
    d = request.json
    yeni_icerik = d.get('YanitIcerik', '').strip()
    if not yeni_icerik:
        return jsonify({'mesaj': 'Yanıt içeriği boş olamaz.', 'durum': False}), 400

    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO firma_gorusu_yanit (GorusID, YanitIcerik, YazanID) VALUES (%s, %s, %s)",
        (gid, yeni_icerik, session['kullanici_id'])
    )
    mysql.connection.commit()
    nid = cur.lastrowid
    cur.close()
    record_log('firma_gorusu_yanit', nid, 'Firma Görüşü Yanıtları', '-', yeni_icerik, LogType.CREATE.value)
    return jsonify({'YanitID': nid})


@firma_gorusu_api_bp.route('/firma_gorusu_yanit/<int:yid>', methods=['PUT'])
@login_required
def firma_gorusu_yanit_guncelle(yid):
    """
    Kendi yanıtını günceller (sadece yazan kullanıcı).
    Body: { YanitIcerik }
    """
    d = request.json
    yeni_icerik = d.get('YanitIcerik', '').strip()
    if not yeni_icerik:
        return jsonify({'mesaj': 'Güncellenecek içerik boş olamaz.', 'durum': False}), 400

    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT YanitIcerik FROM firma_gorusu_yanit WHERE YanitID = %s AND YazanID = %s",
        (yid, session['kullanici_id'])
    )
    eski = cur.fetchone()
    if not eski:
        cur.close()
        return jsonify({'mesaj': 'Yanıt bulunamadı veya yetkiniz yok.', 'durum': False}), 403

    eski_icerik = eski[0]
    cur.execute(
        "UPDATE firma_gorusu_yanit SET YanitIcerik = %s WHERE YanitID = %s AND YazanID = %s",
        (yeni_icerik, yid, session['kullanici_id'])
    )
    guncellenen = cur.rowcount
    mysql.connection.commit()
    cur.close()
    record_log('firma_gorusu_yanit', yid, 'Firma Görüşü Yanıtları', eski_icerik, yeni_icerik, LogType.UPDATE.value)

    if guncellenen > 0:
        return jsonify({'mesaj': 'Yanıt başarıyla güncellendi.', 'durum': True}), 200
    return jsonify({'mesaj': 'İçerik zaten aynı.', 'durum': False}), 200


@firma_gorusu_api_bp.route('/firma_gorusu_yanit/<int:yid>', methods=['DELETE'])
@login_required
def firma_gorusu_yanit_sil(yid):
    """
    Kendi yanıtını siler (sadece yazan kullanıcı).
    """
    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT YanitIcerik FROM firma_gorusu_yanit WHERE YanitID = %s AND YazanID = %s",
        (yid, session['kullanici_id'])
    )
    eski = cur.fetchone()
    if not eski:
        cur.close()
        return jsonify({'mesaj': 'Yanıt bulunamadı veya silme yetkiniz yok.', 'durum': False}), 403

    eski_icerik = eski[0]
    cur.execute(
        "DELETE FROM firma_gorusu_yanit WHERE YanitID = %s AND YazanID = %s",
        (yid, session['kullanici_id'])
    )
    silinen = cur.rowcount
    mysql.connection.commit()
    cur.close()
    record_log('firma_gorusu_yanit', yid, 'Firma Görüşü Yanıtları', eski_icerik, '-', LogType.DELETE.value)

    if silinen > 0:
        return jsonify({'mesaj': 'Yanıt başarıyla silindi.', 'durum': True}), 200
    return jsonify({'mesaj': 'Yanıt bulunamadı veya silme yetkiniz yok.', 'durum': False}), 403
