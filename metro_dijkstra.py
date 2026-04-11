import csv
import heapq
import webbrowser
from collections import defaultdict
import folium

# ------------------------------------------------------------
# CONFIGURAÇÕES
# ------------------------------------------------------------
ARQUIVO_ARESTAS = 'arestas_completas.csv'

# ------------------------------------------------------------
# CARREGAMENTO DO GRAFO
# ------------------------------------------------------------
def carregar_grafo(arquivo):
    grafo = defaultdict(list)
    info = {}                # id -> (nome_pt, nome_original, nome_trans, linha)
    nome_para_ids = defaultdict(list)
    coords = {}              # latitude lontitude
    linha_estacao = {}       # id/nome linha

    with open(arquivo, 'r', encoding='utf-8') as f:
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

            # Informações textuais
            for est_id, nome_pt, nome_orig, nome_trans in [
                (u, row['nome_pt_origem'], row['nome_original_origem'], row['nome_trans_origem']),
                (v, row['nome_pt_destino'], row['nome_original_destino'], row['nome_trans_destino'])
            ]:
                if est_id not in info:
                    info[est_id] = (nome_pt, nome_orig, nome_trans, linha)
                    # Indexa para busca
                    for termo in [nome_pt, nome_orig, nome_trans]:
                        termo_lower = termo.lower()
                        if est_id not in nome_para_ids[termo_lower]:
                            nome_para_ids[termo_lower].append(est_id)

    return grafo, info, nome_para_ids, coords, linha_estacao

# ------------------------------------------------------------
# DIJKSTRA
# ------------------------------------------------------------
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

# ------------------------------------------------------------
# BUSCA DE ESTAÇÕES
# ------------------------------------------------------------
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

# ------------------------------------------------------------
# GERAÇÃO DE MAPA COM FOLIUM
# ------------------------------------------------------------
def gerar_mapa(grafo, coords, linha_estacao, info, caminho=None):
    # Paleta de cores para as linhas
    cores_linhas = {}
    paleta = [
        '#e6194B', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4',
        '#42d4f4', '#f032e6', '#bfef45', '#fabed4', '#469990', '#dcbeff',
        '#9A6324', '#fffac8', '#800000', '#aaffc3', '#808000', '#ffd8b1'
    ]
    for i, linha in enumerate(set(linha_estacao.values())):
        cores_linhas[linha] = paleta[i % len(paleta)]

    # Mapa base CartoDB Voyager (sem trilhos de metrô, visual limpo)
    mapa = folium.Map(
        location=[55.7558, 37.6173],
        zoom_start=11,
        tiles='CartoDB voyager',   # ou 'CartoDB positron' para fundo claro
        attr='CartoDB'
    )

# --- DESENHA AS ARESTAS (somente se ambas as pontas têm coordenadas) ---
    arestas_desenhadas = set()
    for u, vizinhos in grafo.items():
        if u not in coords:
            continue
        lat_u, lon_u = coords[u]
        for v, _ in vizinhos:
            if v not in coords:
                continue
            aresta = tuple(sorted((u, v)))
            if aresta in arestas_desenhadas:
                continue
            arestas_desenhadas.add(aresta)
            
            lat_v, lon_v = coords[v]
            linha = linha_estacao.get(u, 'Desconhecida')
            cor = cores_linhas.get(linha, 'gray')
            
            folium.PolyLine(
                locations=[(lat_u, lon_u), (lat_v, lon_v)],
                color=cor,
                weight=4.5,
                opacity=0.85
            ).add_to(mapa)

    # Marcadores das estações (círculos discretos)
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

    # Destaca a rota
    if caminho:
        for i in range(len(caminho)-1):
            u, v = caminho[i], caminho[i+1]
            if u in coords and v in coords:
                folium.PolyLine(
                    locations=[coords[u], coords[v]],
                    color='#FFD700',   # amarelo ouro
                    weight=8,
                    opacity=1.0,
                    smooth_factor=0.5
                ).add_to(mapa)

        # Ícones de início e fim (usando Font Awesome)
        folium.Marker(
            location=coords[caminho[0]],
            popup=f"<b>INÍCIO:</b><br>{info[caminho[0]][0]}",
            icon=folium.Icon(color='green', icon='play', prefix='fa')
        ).add_to(mapa)
        folium.Marker(
            location=coords[caminho[-1]],
            popup=f"<b>DESTINO:</b><br>{info[caminho[-1]][0]}",
            icon=folium.Icon(color='red', icon='stop', prefix='fa')
        ).add_to(mapa)

    # Adiciona legenda simples das linhas (opcional)
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

# ------------------------------------------------------------
# INTERFACE PRINCIPAL
# ------------------------------------------------------------
def main():
    print("🔄 Carregando dados do metrô de Moscou...")
    try:
        grafo, info, nome_para_ids, coords, linha_estacao = carregar_grafo(ARQUIVO_ARESTAS)
    except FileNotFoundError:
        print(f"❌ Arquivo '{ARQUIVO_ARESTAS}' não encontrado.")
        print("   Execute primeiro: python gerar_grafo_final.py")
        return

    print(f"✅ {len(grafo)} estações carregadas.\n")

    # ========== CÓDIGO DE DEPURAÇÃO ==========
    # Verificar Govorovo e Minskaya
    govorovo_id = '149'
    minskaya_id = '154'
    
    if govorovo_id in grafo:
        print(f"✅ Govorovo (ID {govorovo_id}) está no grafo.")
        print(f"   Conexões: {grafo[govorovo_id][:5]}")  # até 5 vizinhos
    else:
        print(f"❌ Govorovo (ID {govorovo_id}) NÃO está no grafo.")
        print(f"   IDs no grafo que começam com 149: {[k for k in grafo.keys() if k.startswith('149')]}")
    
    if minskaya_id in grafo:
        print(f"✅ Minskaya (ID {minskaya_id}) está no grafo.")
        print(f"   Conexões: {grafo[minskaya_id][:5]}")
    else:
        print(f"❌ Minskaya (ID {minskaya_id}) NÃO está no grafo.")
        print(f"   IDs no grafo que começam com 154: {[k for k in grafo.keys() if k.startswith('154')]}")
    
    print("\n" + "="*50 + "\n")

    # Verificar caminho completo
    caminho_teste = ['149', '150', '151', '152', '153', '154']
    for i in range(len(caminho_teste)-1):
        u, v = caminho_teste[i], caminho_teste[i+1]
        if u in grafo:
            vizinhos = [viz for viz, _ in grafo[u]]
            if v in vizinhos:
                print(f"✅ Aresta {u} → {v} existe.")
            else:
                print(f"❌ Aresta {u} → {v} NÃO existe! Vizinhos de {u}: {vizinhos}")
        else:
            print(f"❌ Estação {u} não está no grafo.")
    # ========== FIM DA DEPURAÇÃO ==========

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
        escolha = int(input("Número: ")) - 1
        if escolha < 0 or escolha >= len(res_orig):
            print("❌ Inválido.")
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
        escolha = int(input("Número: ")) - 1
        if escolha < 0 or escolha >= len(res_dest):
            print("❌ Inválido.")
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
            gerar_mapa(grafo, coords, linha_estacao, info, caminho)
            print("   Mapa salvo como 'rota_metro.html' e aberto no navegador.")

        if input("\nNova consulta? (s/n): ").lower() != 's':
            break

if __name__ == "__main__":
    main()