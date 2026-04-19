"""
Denetim Logu API Controller'ı (Blueprint)
"""
from flask import Blueprint, jsonify, request
from app.utils.database import mysql
from app.utils.auth import login_required

audit_log_api_bp = Blueprint('audit_log_api', __name__, url_prefix='/api')


@audit_log_api_bp.route('/log', methods=['GET'])
@login_required
def log_listesi():
    """
    Değişiklik loglarını listeler.
    Query params:
      - tablo     : TabloAdi filtresi (opsiyonel)
      - kayit_id  : KayitID filtresi (opsiyonel)
      - tur       : LogType filtresi — Ekleme / Güncelleme / Silme (opsiyonel)
      - limit     : max satır sayısı (varsayılan 500)
    """
    tablo     = request.args.get('tablo')
    kayit_id  = request.args.get('kayit_id')
    tur       = request.args.get('tur')
    limit     = int(request.args.get('limit', 500))

    cur = mysql.connection.cursor(__import__('MySQLdb').cursors.DictCursor)
    q = "SELECT * FROM degisiklik_log WHERE 1=1"
    params = []

    if tablo:
        q += " AND TabloAdi=%s"
        params.append(tablo)
    if kayit_id:
        q += " AND KayitID=%s"
        params.append(kayit_id)
    if tur:
        q += " AND Tur=%s"
        params.append(tur)

    q += " ORDER BY DegisimTarihi DESC LIMIT %s"
    params.append(limit)

    cur.execute(q, params)
    d = cur.fetchall()
    for r in d:
        if r.get('DegisimTarihi'):
            r['DegisimTarihi'] = r['DegisimTarihi'].strftime('%d.%m.%Y %H:%M:%S')
    cur.close()
    return jsonify(d)


@audit_log_api_bp.route('/log/<int:log_id>', methods=['DELETE'])
@login_required
def log_sil(log_id):
    """Tek bir log kaydını siler (admin işlemi)."""
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM degisiklik_log WHERE LogID=%s", (log_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'ok': True})


@audit_log_api_bp.route('/log/temizle', methods=['DELETE'])
@login_required
def log_temizle():
    """
    Belirli kriterlere göre log temizleme (admin işlemi).
    Body (JSON, tamamı opsiyonel):
      - tablo    : sadece bu tablonun loglarını sil
      - tur      : sadece bu türdeki logları sil
      - gun_once : kaç günden eski logları sil (varsayılan 90)
    """
    d = request.json or {}
    tablo    = d.get('tablo')
    tur      = d.get('tur')
    gun_once = int(d.get('gun_once', 90))

    cur = mysql.connection.cursor()
    q = "DELETE FROM degisiklik_log WHERE DegisimTarihi < DATE_SUB(NOW(), INTERVAL %s DAY)"
    params = [gun_once]

    if tablo:
        q += " AND TabloAdi=%s"
        params.append(tablo)
    if tur:
        q += " AND Tur=%s"
        params.append(tur)

    cur.execute(q, params)
    silinen = cur.rowcount
    mysql.connection.commit()
    cur.close()
    return jsonify({'ok': True, 'silinen': silinen})
