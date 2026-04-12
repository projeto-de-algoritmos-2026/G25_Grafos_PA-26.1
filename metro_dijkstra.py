import csv
import heapq
import webbrowser
from collections import defaultdict
import folium


# CONFIGURAÇÕES

ARQUIVO_ARESTAS = 'arestas_completas.csv'
ARQUIVO_ESTACOES = 'metro_moscou.csv'


# CARREGAMENTO DO GRAFO

def carregar_grafo(arquivo_arestas, arquivo_estacoes):
    grafo = defaultdict(list)
    info = {}                # id -> (nome_pt, nome_original, nome_trans, linha)
    nome_para_ids = defaultdict(list)
    coords = {}              # id -> (lat, lon)
    linha_estacao = {}       # id -> nome da linha

    # Carregar ordem das estações por linha (para desenho contínuo)
    linhas_estacoes = defaultdict(list)
    with open(arquivo_estacoes, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            id_simples = row[0]
            linha = row[3]
            linhas_estacoes[linha].append(id_simples)

    with open(arquivo_arestas, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            u = str(row['origem_id'])
            v = str(row['destino_id'])
            tempo = int(row['tempo_seg'])

            grafo[u].append((v, tempo))
            grafo[v].append((u, tempo))

            lat_u = float(row['lat_origem']) if row['lat_origem'] else None
            lon_u = float(row['lon_origem']) if row['lon_origem'] else None
            lat_v = float(row['lat_destino']) if row['lat_destino'] else None
            lon_v = float(row['lon_destino']) if row['lon_destino'] else None
            if lat_u and lon_u:
                coords[u] = (lat_u, lon_u)
            if lat_v and lon_v:
                coords[v] = (lat_v, lon_v)

            linha = row['linha_origem']
            linha_estacao[u] = linha
            linha_estacao[v] = linha

            for est_id, nome_pt, nome_orig, nome_trans in [
                (u, row['nome_pt_origem'], row['nome_original_origem'], row['nome_trans_origem']),
                (v, row['nome_pt_destino'], row['nome_original_destino'], row['nome_trans_destino'])
            ]:
                if est_id not in info:
                    info[est_id] = (nome_pt, nome_orig, nome_trans, linha)
                    for termo in [nome_pt, nome_orig, nome_trans]:
                        termo_lower = termo.lower()
                        if est_id not in nome_para_ids[termo_lower]:
                            nome_para_ids[termo_lower].append(est_id)

    return grafo, info, nome_para_ids, coords, linha_estacao, linhas_estacoes


# DIJKSTRA

def dijkstra(grafo, origem, destino):
    dist = {origem: 0}
    prev = {}
    fila = [(0, origem)]
    visitados = set()

    while fila:
        d, u = heapq.heappop(fila)
        if u in visitados:
            continue
        visitados.add(u)
        if u == destino:
            break
        for v, w in grafo.get(u, []):
            nd = d + w
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(fila, (nd, v))

    if destino not in dist:
        return None, None

    caminho = []
    cur = destino
    while cur != origem:
        caminho.append(cur)
        cur = prev[cur]
    caminho.append(origem)
    caminho.reverse()
    return dist[destino], caminho


# BUSCA DE ESTAÇÕES

def buscar_estacao(termo, nome_para_ids, info):
    termo = termo.lower()
    resultados = []
    vistos = set()
    for chave, ids in nome_para_ids.items():
        if termo in chave:
            for id_est in ids:
                if id_est not in vistos:
                    vistos.add(id_est)
                    nome_pt, nome_orig, nome_trans, linha = info.get(id_est, (id_est, id_est, id_est, '?'))
                    resultados.append((id_est, nome_pt, linha))
    return resultados


# GERAÇÃO DE MAPA COM FOLIUM
def gerar_mapa(grafo, coords, linha_estacao, info, linhas_estacoes, caminho=None):
    # Paleta de cores para as linhas
    cores_linhas = {}
    paleta = [
        '#e6194B', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4',
        '#42d4f4', '#f032e6', '#bfef45', '#fabed4', '#469990', '#dcbeff',
        '#9A6324', '#fffac8', '#800000', '#aaffc3', '#808000', '#ffd8b1'
    ]
    for i, linha in enumerate(set(linha_estacao.values())):
        cores_linhas[linha] = paleta[i % len(paleta)]

    # Mapa base CartoDB Voyager (limpo)
    mapa = folium.Map(
        location=[55.7558, 37.6173],
        zoom_start=11,
        tiles='CartoDB voyager',
        attr='CartoDB'
    )

    # --- Desenha conexões contínuas por linha (ignorando estações sem coordenadas) ---
    for linha, ids in linhas_estacoes.items():
        cor = cores_linhas.get(linha, 'gray')
        ultima_com_coord = None
        for est_id in ids:
            if est_id in coords:
                if ultima_com_coord is not None:
                    folium.PolyLine(
                        locations=[coords[ultima_com_coord], coords[est_id]],
                        color=cor,
                        weight=4.5,
                        opacity=0.85
                    ).add_to(mapa)
                ultima_com_coord = est_id

    # --- Desenha também arestas de baldeação (entre linhas diferentes) ---
    arestas_desenhadas = set()
    for u, vizinhos in grafo.items():
        if u not in coords:
            continue
        for v, _ in vizinhos:
            if v not in coords:
                continue
            aresta = tuple(sorted((u, v)))
            if aresta in arestas_desenhadas:
                continue
            arestas_desenhadas.add(aresta)
            linha = linha_estacao.get(u, 'Desconhecida')
            cor = cores_linhas.get(linha, 'gray')
            folium.PolyLine(
                locations=[coords[u], coords[v]],
                color=cor,
                weight=4.5,
                opacity=0.85
            ).add_to(mapa)

    # --- Marcadores das estações ---
    for est_id, (lat, lon) in coords.items():
        nome_pt, _, _, _ = info.get(est_id, (est_id, '', '', ''))
        folium.CircleMarker(
            location=(lat, lon),
            radius=5,
            color='#333333',
            fill=True,
            fill_color='white',
            fill_opacity=1.0,
            weight=1.5,
            popup=folium.Popup(nome_pt, max_width=200)
        ).add_to(mapa)

    # --- Destaca a rota ---
    if caminho:
        for i in range(len(caminho)-1):
            u, v = caminho[i], caminho[i+1]
            if u in coords and v in coords:
                folium.PolyLine(
                    locations=[coords[u], coords[v]],
                    color='#FFD700',
                    weight=8,
                    opacity=1.0
                ).add_to(mapa)

        if caminho[0] in coords:
            folium.Marker(
                location=coords[caminho[0]],
                popup=f"<b>INÍCIO:</b><br>{info[caminho[0]][0]}",
                icon=folium.Icon(color='green', icon='play', prefix='fa')
            ).add_to(mapa)
        if caminho[-1] in coords:
            folium.Marker(
                location=coords[caminho[-1]],
                popup=f"<b>DESTINO:</b><br>{info[caminho[-1]][0]}",
                icon=folium.Icon(color='red', icon='stop', prefix='fa')
            ).add_to(mapa)


    legend_html = '''
    <div style="position: fixed; bottom: 20px; left: 20px; width: 200px; 
                background: white; border:2px solid grey; z-index:9999; 
                font-size:12px; padding: 10px; border-radius: 6px;
                max-height: 300px; overflow-y: auto;">
    <b>Linhas do Metrô</b><br>
    '''
    for linha, cor in cores_linhas.items():
        legend_html += f'<span style="color:{cor};">⬤</span> {linha}<br>'
    legend_html += '</div>'
    mapa.get_root().html.add_child(folium.Element(legend_html))

    mapa.save('rota_metro.html')
    webbrowser.open('rota_metro.html')


# INTERFACE PRINCIPAL

def main():
    print("🔄 Carregando dados do metrô de Moscou...")
    try:
        grafo, info, nome_para_ids, coords, linha_estacao, linhas_estacoes = carregar_grafo(ARQUIVO_ARESTAS, ARQUIVO_ESTACOES)
    except FileNotFoundError as e:
        print(f"❌ Arquivo não encontrado: {e}")
        print("   Certifique-se de que 'arestas_completas.csv' e 'metro_moscou.csv' estão na pasta.")
        return

    print(f"✅ {len(grafo)} estações carregadas.\n")

    while True:
        print("\n" + "-"*40)
        termo = input("🔍 Estação de origem (parte do nome ou 'sair'): ").strip()
        if termo.lower() == 'sair':
            break
        res_orig = buscar_estacao(termo, nome_para_ids, info)
        if not res_orig:
            print("❌ Nenhuma estação encontrada.")
            continue
        print("\nEstações encontradas:")
        for i, (id_est, nome, linha) in enumerate(res_orig[:10], 1):
            print(f"   {i}. {nome} (Linha {linha})")
        try:
            escolha = int(input("Número: ")) - 1
        except ValueError:
            print("❌ Entrada inválida.")
            continue
        if escolha < 0 or escolha >= len(res_orig):
            print("❌ Número inválido.")
            continue
        id_origem = res_orig[escolha][0]

        termo = input("\n🔍 Estação de destino: ").strip()
        res_dest = buscar_estacao(termo, nome_para_ids, info)
        if not res_dest:
            print("❌ Nenhuma estação encontrada.")
            continue
        print("\nEstações encontradas:")
        for i, (id_est, nome, linha) in enumerate(res_dest[:10], 1):
            print(f"   {i}. {nome} (Linha {linha})")
        try:
            escolha = int(input("Número: ")) - 1
        except ValueError:
            print("❌ Entrada inválida.")
            continue
        if escolha < 0 or escolha >= len(res_dest):
            print("❌ Número inválido.")
            continue
        id_destino = res_dest[escolha][0]

        print("\n🔄 Calculando rota...")
        tempo, caminho = dijkstra(grafo, id_origem, id_destino)
        if caminho is None:
            print("❌ Rota não encontrada.")
        else:
            print(f"✅ Tempo estimado: {tempo//60} min {tempo%60} seg")
            print("📍 Estações:")
            for i, est in enumerate(caminho):
                nome, _, _, linha = info[est]
                print(f"   {i+1}. {nome} (Linha {linha})")
            print("\n🗺️ Gerando mapa...")
            gerar_mapa(grafo, coords, linha_estacao, info, linhas_estacoes, caminho)
            print("   Mapa salvo como 'rota_metro.html' e aberto no navegador.")

        if input("\nNova consulta? (s/n): ").lower() != 's':
            break

    print("\n👋 Obrigado por usar o planejador de rotas do Metrô de Moscou!")

if __name__ == "__main__":
    main()