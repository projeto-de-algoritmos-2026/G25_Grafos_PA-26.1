import csv
import math
import urllib.request
from collections import defaultdict
import time
import requests

# ------------------------------------------------------------
# CONFIGURAÇÕES
# ------------------------------------------------------------
ARQUIVO_METRO_CSV = 'metro_moscou.csv'
ARQUIVO_SAIDA = 'arestas_completas.csv'

URL_ESTACOES = "https://raw.githubusercontent.com/nalgeon/metro/main/data/station.ru.csv"
URL_LINHAS   = "https://raw.githubusercontent.com/nalgeon/metro/main/data/line.ru.csv"

VELOCIDADE_MEDIA_KPH = 41.62
TEMPO_PARADA_SEG = 60
vel_km_s = VELOCIDADE_MEDIA_KPH / 3600.0

# Cache de coordenadas obtidas via API
coordenadas_api_cache = {}

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def transliterate_russian(text):
    if not text:
        return text
    mapping = {
        'А':'A','а':'a','Б':'B','б':'b','В':'V','в':'v','Г':'G','г':'g',
        'Д':'D','д':'d','Е':'E','е':'e','Ё':'Yo','ё':'yo','Ж':'Zh','ж':'zh',
        'З':'Z','з':'z','И':'I','и':'i','Й':'Y','й':'y','К':'K','к':'k',
        'Л':'L','л':'l','М':'M','м':'m','Н':'N','н':'n','О':'O','о':'o',
        'П':'P','п':'p','Р':'R','р':'r','С':'S','с':'s','Т':'T','т':'t',
        'У':'U','у':'u','Ф':'F','ф':'f','Х':'Kh','х':'kh','Ц':'Ts','ц':'ts',
        'Ч':'Ch','ч':'ch','Ш':'Sh','ш':'sh','Щ':'Shch','щ':'shch','Ъ':'',
        'ъ':'','Ы':'Y','ы':'y','Ь':'','ь':'','Э':'E','э':'e','Ю':'Yu','ю':'yu',
        'Я':'Ya','я':'ya'
    }
    return ''.join(mapping.get(c, c) for c in text)

def coordenada_valida(lat, lon):
    """Verifica se lat/lon são números válidos dentro da região de Moscou."""
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (ValueError, TypeError):
        return False
    return (55.0 <= lat_f <= 56.0) and (37.0 <= lon_f <= 38.0)

def buscar_coordenadas_api(nome_original):
    """Busca coordenadas via Nominatim com cache."""
    if nome_original in coordenadas_api_cache:
        return coordenadas_api_cache[nome_original]
    
    query = f"станция метро {nome_original}, Москва"
    url = "https://nominatim.openstreetmap.org/search"
    params = {'q': query, 'format': 'json', 'limit': 1, 'accept-language': 'ru'}
    headers = {'User-Agent': 'MetroMoscouProjeto/1.0 (contato: seuemail@exemplo.com)'}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                coordenadas_api_cache[nome_original] = (lat, lon)
                return lat, lon
    except Exception:
        pass
    
    coordenadas_api_cache[nome_original] = (None, None)
    return None, None

print("📥 Baixando dados oficiais (coordenadas e linhas)...")

# --- Linhas ---
try:
    with urllib.request.urlopen(URL_LINHAS) as f:
        lines_data = f.read().decode('utf-8')
except Exception as e:
    print(f"❌ Erro ao baixar linhas: {e}")
    exit(1)

linhas = {}
reader = csv.reader(lines_data.splitlines())
next(reader)
for row in reader:
    if len(row) >= 3:
        linhas[row[0]] = row[2]

# --- Estações (coordenadas do nalgeon) ---
try:
    with urllib.request.urlopen(URL_ESTACOES) as f:
        stations_data = f.read().decode('utf-8')
except Exception as e:
    print(f"❌ Erro ao baixar estações: {e}")
    exit(1)

estacoes_nalgeon = {}
reader = csv.reader(stations_data.splitlines())
next(reader)
for row in reader:
    if len(row) < 7:
        continue
    id_cidade = row[1]
    if id_cidade != '1':
        continue
    nome_original = row[3].strip()
    lat = float(row[4])
    lon = float(row[5])
    if coordenada_valida(lat, lon):
        estacoes_nalgeon[nome_original] = (lat, lon)

print(f"✅ Coordenadas carregadas para {len(estacoes_nalgeon)} estações (dataset nalgeon).")

# --- Carregar CSV gerado do metrostations ---
print("📂 Carregando seu arquivo metro_moscou.csv...")
estacoes_metro = []
linhas_estacoes = defaultdict(list)

with open(ARQUIVO_METRO_CSV, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        id_simples = row[0]
        nome_original = row[1].strip()
        nome_pt = row[2]
        linha = row[3]
        conexoes_str = row[4] if len(row) > 4 else ''
        conexoes = [c.strip() for c in conexoes_str.split(',') if c.strip()]
        estacoes_metro.append((id_simples, nome_original, nome_pt, linha, conexoes))
        linhas_estacoes[linha].append(id_simples)

print(f"✅ Seu CSV carregado: {len(estacoes_metro)} estações.")

# --- Construir arestas consecutivas e de baldeação ---
arestas = set()
for linha, ids in linhas_estacoes.items():
    for i in range(len(ids)-1):
        u, v = ids[i], ids[i+1]
        arestas.add(tuple(sorted((u, v))))

info_dict = {e[0]: e for e in estacoes_metro}
for id_simples, _, _, _, conexoes in estacoes_metro:
    for viz in conexoes:
        if viz in info_dict:
            arestas.add(tuple(sorted((id_simples, viz))))

print(f"🔗 Total de arestas únicas: {len(arestas)}")

# --- Verificar e completar coordenadas (SEM fallback central) ---
print("\n🔍 Verificando coordenadas das estações...")
coordenadas_finais = {}  # id_simples -> (lat, lon) ou (None, None)

for id_simples, nome_original, _, _, _ in estacoes_metro:
    if nome_original in estacoes_nalgeon:
        lat, lon = estacoes_nalgeon[nome_original]
        if coordenada_valida(lat, lon):
            coordenadas_finais[id_simples] = (lat, lon)
            continue
    coordenadas_finais[id_simples] = (None, None)

faltantes = [id_simples for id_simples, coord in coordenadas_finais.items() if coord[0] is None]
print(f"⚠️ {len(faltantes)} estações com coordenadas ausentes ou inválidas.")

if faltantes:
    print("🌍 Buscando coordenadas na API Nominatim (pode levar alguns minutos)...")
    for i, id_simples in enumerate(faltantes, 1):
        _, nome_original, _, _, _ = info_dict[id_simples]
        print(f"   [{i}/{len(faltantes)}] {nome_original}")
        lat, lon = buscar_coordenadas_api(nome_original)
        if lat and lon and coordenada_valida(lat, lon):
            coordenadas_finais[id_simples] = (lat, lon)
        else:
            coordenadas_finais[id_simples] = (None, None)   # sem fallback
        time.sleep(1.5)

# --- Gerar CSV final ---
print("\n⏳ Calculando distâncias e tempos...")
with open(ARQUIVO_SAIDA, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow([
        'origem_id', 'destino_id', 'tempo_seg', 'distancia_km',
        'nome_original_origem', 'nome_pt_origem', 'nome_trans_origem',
        'nome_original_destino', 'nome_pt_destino', 'nome_trans_destino',
        'linha_origem', 'lat_origem', 'lon_origem', 'lat_destino', 'lon_destino'
    ])

    for u, v in arestas:
        if u not in info_dict or v not in info_dict:
            continue
        id_u, nome_orig_u, nome_pt_u, linha_u, _ = info_dict[u]
        id_v, nome_orig_v, nome_pt_v, linha_v, _ = info_dict[v]
        nome_trans_u = transliterate_russian(nome_orig_u)
        nome_trans_v = transliterate_russian(nome_orig_v)

        lat_u, lon_u = coordenadas_finais[u]
        lat_v, lon_v = coordenadas_finais[v]

        if lat_u is not None and lon_u is not None and lat_v is not None and lon_v is not None:
            dist = haversine(lat_u, lon_u, lat_v, lon_v)
            if dist < 0.1:
                dist = 0.5
        else:
            dist = 1.81   # distância média padrão

        tempo = int(round(dist / vel_km_s + TEMPO_PARADA_SEG))
        nome_linha = linhas.get(linha_u, linha_u)

        writer.writerow([
            u, v, tempo, round(dist, 3),
            nome_orig_u, nome_pt_u, nome_trans_u,
            nome_orig_v, nome_pt_v, nome_trans_v,
            nome_linha,
            lat_u if lat_u is not None else '',
            lon_u if lon_u is not None else '',
            lat_v if lat_v is not None else '',
            lon_v if lon_v is not None else ''
        ])

print(f"🎉 Arquivo '{ARQUIVO_SAIDA}' gerado com sucesso!")