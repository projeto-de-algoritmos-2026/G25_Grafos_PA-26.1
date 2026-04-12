import csv
import heapq
import os
import webbrowser
from collections import defaultdict, deque
import tkinter as tk
from tkinter import ttk, messagebox

import folium

# ------------------------------------------------------------
# CONFIGURACOES
# ------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_ARESTAS = os.path.join(BASE_DIR, "arestas_completas.csv")
ARQUIVO_ESTACOES = os.path.join(BASE_DIR, "metro_moscou.csv")


# ------------------------------------------------------------
# CARREGAMENTO DO GRAFO
# ------------------------------------------------------------
def carregar_grafo(arquivo_arestas, arquivo_estacoes):
    grafo = defaultdict(list)
    info = {}                # id -> (nome_pt, nome_original, nome_trans, linha)
    nome_para_ids = defaultdict(list)
    coords = {}              # id -> (lat, lon)
    linha_estacao = {}       # id -> nome da linha

    # Carregar ordem das estacoes por linha (para desenho continuo)
    linhas_estacoes = defaultdict(list)
    with open(arquivo_estacoes, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            id_simples = row[0]
            linha = row[3]
            linhas_estacoes[linha].append(id_simples)

    with open(arquivo_arestas, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            u = str(row["origem_id"])
            v = str(row["destino_id"])
            tempo = int(row["tempo_seg"])

            grafo[u].append((v, tempo))
            grafo[v].append((u, tempo))

            lat_u = float(row["lat_origem"]) if row["lat_origem"] else None
            lon_u = float(row["lon_origem"]) if row["lon_origem"] else None
            lat_v = float(row["lat_destino"]) if row["lat_destino"] else None
            lon_v = float(row["lon_destino"]) if row["lon_destino"] else None
            if lat_u and lon_u:
                coords[u] = (lat_u, lon_u)
            if lat_v and lon_v:
                coords[v] = (lat_v, lon_v)

            linha = row["linha_origem"]
            linha_estacao[u] = linha
            linha_estacao[v] = linha

            for est_id, nome_pt, nome_orig, nome_trans in [
                (u, row["nome_pt_origem"], row["nome_original_origem"], row["nome_trans_origem"]),
                (v, row["nome_pt_destino"], row["nome_original_destino"], row["nome_trans_destino"]),
            ]:
                if est_id not in info:
                    info[est_id] = (nome_pt, nome_orig, nome_trans, linha)
                    for termo in [nome_pt, nome_orig, nome_trans]:
                        termo_lower = termo.lower()
                        if est_id not in nome_para_ids[termo_lower]:
                            nome_para_ids[termo_lower].append(est_id)

    return grafo, info, nome_para_ids, coords, linha_estacao, linhas_estacoes


# ------------------------------------------------------------
# DIJKSTRA (MENOR TEMPO)
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
# BFS (MENOR NUMERO DE TRECHOS/ESTACOES)
# ------------------------------------------------------------
def bfs_menor_estacoes(grafo, origem, destino):
    fila = deque([origem])
    visitados = {origem}
    prev = {}

    while fila:
        u = fila.popleft()
        if u == destino:
            break

        for v, _ in grafo.get(u, []):
            if v not in visitados:
                visitados.add(v)
                prev[v] = u
                fila.append(v)

    if destino not in visitados:
        return None

    caminho = []
    cur = destino
    while cur != origem:
        caminho.append(cur)
        cur = prev[cur]
    caminho.append(origem)
    caminho.reverse()
    return caminho


def calcular_tempo_caminho(grafo, caminho):
    if not caminho or len(caminho) < 2:
        return 0

    total = 0
    for i in range(len(caminho) - 1):
        u, v = caminho[i], caminho[i + 1]
        peso = None
        for viz, tempo in grafo.get(u, []):
            if viz == v:
                peso = tempo
                break
        if peso is None:
            return None
        total += peso
    return total


# ------------------------------------------------------------
# GERACAO DE MAPA COM FOLIUM
# ------------------------------------------------------------
def gerar_mapa(grafo, coords, linha_estacao, info, linhas_estacoes, caminho=None, nome_arquivo="rota_metro.html"):
    cores_linhas = {}
    paleta = [
        "#e6194B", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4",
        "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990", "#dcbeff",
        "#9A6324", "#fffac8", "#800000", "#aaffc3", "#808000", "#ffd8b1",
    ]
    for i, linha in enumerate(set(linha_estacao.values())):
        cores_linhas[linha] = paleta[i % len(paleta)]

    mapa = folium.Map(
        location=[55.7558, 37.6173],
        zoom_start=11,
        tiles="CartoDB voyager",
        attr="CartoDB",
    )

    for linha, ids in linhas_estacoes.items():
        cor = cores_linhas.get(linha, "gray")
        ultima_com_coord = None
        for est_id in ids:
            if est_id in coords:
                if ultima_com_coord is not None:
                    folium.PolyLine(
                        locations=[coords[ultima_com_coord], coords[est_id]],
                        color=cor,
                        weight=4.5,
                        opacity=0.85,
                    ).add_to(mapa)
                ultima_com_coord = est_id

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
            linha = linha_estacao.get(u, "Desconhecida")
            cor = cores_linhas.get(linha, "gray")
            folium.PolyLine(
                locations=[coords[u], coords[v]],
                color=cor,
                weight=4.5,
                opacity=0.85,
            ).add_to(mapa)

    for est_id, (lat, lon) in coords.items():
        nome_pt, _, _, _ = info.get(est_id, (est_id, "", "", ""))
        folium.CircleMarker(
            location=(lat, lon),
            radius=5,
            color="#333333",
            fill=True,
            fill_color="white",
            fill_opacity=1.0,
            weight=1.5,
            popup=folium.Popup(nome_pt, max_width=200),
        ).add_to(mapa)

    if caminho:
        for i in range(len(caminho) - 1):
            u, v = caminho[i], caminho[i + 1]
            if u in coords and v in coords:
                folium.PolyLine(
                    locations=[coords[u], coords[v]],
                    color="#FFD700",
                    weight=8,
                    opacity=1.0,
                ).add_to(mapa)

        if caminho[0] in coords:
            folium.Marker(
                location=coords[caminho[0]],
                popup=f"<b>INICIO:</b><br>{info[caminho[0]][0]}",
                icon=folium.Icon(color="green", icon="play", prefix="fa"),
            ).add_to(mapa)
        if caminho[-1] in coords:
            folium.Marker(
                location=coords[caminho[-1]],
                popup=f"<b>DESTINO:</b><br>{info[caminho[-1]][0]}",
                icon=folium.Icon(color="red", icon="stop", prefix="fa"),
            ).add_to(mapa)

    legend_html = """
    <div style="position: fixed; bottom: 20px; left: 20px; width: 200px;
                background: white; border:2px solid grey; z-index:9999;
                font-size:12px; padding: 10px; border-radius: 6px;
                max-height: 300px; overflow-y: auto;">
    <b>Linhas do Metro</b><br>
    """
    for linha, cor in cores_linhas.items():
        legend_html += f'<span style="color:{cor};">⬤</span> {linha}<br>'
    legend_html += "</div>"
    mapa.get_root().html.add_child(folium.Element(legend_html))

    caminho_saida = os.path.join(BASE_DIR, nome_arquivo)
    mapa.save(caminho_saida)
    webbrowser.open(caminho_saida)


class MetroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Metro de Moscou - Dijkstra x BFS")
        self.root.geometry("900x650")

        try:
            (
                self.grafo,
                self.info,
                _,
                self.coords,
                self.linha_estacao,
                self.linhas_estacoes,
            ) = carregar_grafo(ARQUIVO_ARESTAS, ARQUIVO_ESTACOES)
        except FileNotFoundError as e:
            messagebox.showerror("Erro", f"Arquivo nao encontrado: {e}")
            self.root.destroy()
            return

        self.opcoes_estacao, self.label_para_id = self._montar_opcoes_estacoes()
        self._montar_layout()

    def _montar_opcoes_estacoes(self):
        pares = []
        for est_id, (nome_pt, _, _, linha) in self.info.items():
            label = f"{nome_pt} | Linha {linha} | ID {est_id}"
            pares.append((label, est_id))
        pares.sort(key=lambda x: x[0].lower())
        opcoes = [p[0] for p in pares]
        label_para_id = {p[0]: p[1] for p in pares}
        return opcoes, label_para_id

    def _montar_layout(self):
        frame_topo = ttk.Frame(self.root, padding=12)
        frame_topo.pack(fill="x")

        ttk.Label(frame_topo, text="Origem:").grid(row=0, column=0, sticky="w")
        self.cb_origem = ttk.Combobox(frame_topo, width=70)
        self.cb_origem.grid(row=0, column=1, sticky="we", padx=8, pady=4)

        ttk.Label(frame_topo, text="Destino:").grid(row=1, column=0, sticky="w")
        self.cb_destino = ttk.Combobox(frame_topo, width=70)
        self.cb_destino.grid(row=1, column=1, sticky="we", padx=8, pady=4)

        self.cb_origem["values"] = self.opcoes_estacao
        self.cb_destino["values"] = self.opcoes_estacao

        self.cb_origem.bind("<KeyRelease>", lambda e: self._filtrar_combobox(self.cb_origem))
        self.cb_destino.bind("<KeyRelease>", lambda e: self._filtrar_combobox(self.cb_destino))

        ttk.Label(frame_topo, text="Algoritmo:").grid(row=2, column=0, sticky="w")
        self.cb_algoritmo = ttk.Combobox(
            frame_topo,
            values=["Dijkstra", "BFS", "Comparar"],
            state="readonly",
            width=20,
        )
        self.cb_algoritmo.current(0)
        self.cb_algoritmo.grid(row=2, column=1, sticky="w", padx=8, pady=8)

        frame_topo.columnconfigure(1, weight=1)

        frame_botoes = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        frame_botoes.pack(fill="x")

        ttk.Button(frame_botoes, text="Calcular rota", command=self.calcular).pack(side="left", padx=(0, 8))
        ttk.Button(frame_botoes, text="Limpar", command=self.limpar).pack(side="left", padx=(0, 8))
        ttk.Button(frame_botoes, text="Sair", command=self.root.destroy).pack(side="left")

        frame_saida = ttk.Frame(self.root, padding=12)
        frame_saida.pack(fill="both", expand=True)

        ttk.Label(frame_saida, text="Resultado:").pack(anchor="w")
        self.txt_saida = tk.Text(frame_saida, wrap="word", height=25)
        self.txt_saida.pack(fill="both", expand=True)

        self._escrever("Projeto carregado com sucesso.")
        self._escrever("Selecione origem e destino, escolha o algoritmo e clique em 'Calcular rota'.")

    def _filtrar_combobox(self, cb):
        termo = cb.get().lower().strip()
        if not termo:
            cb["values"] = self.opcoes_estacao
            return
        filtradas = [o for o in self.opcoes_estacao if termo in o.lower()]
        cb["values"] = filtradas if filtradas else self.opcoes_estacao

    def _escrever(self, texto=""):
        self.txt_saida.insert("end", texto + "\n")
        self.txt_saida.see("end")

    def _obter_id_estacao(self, texto_digitado):
        if texto_digitado in self.label_para_id:
            return self.label_para_id[texto_digitado]

        termo = texto_digitado.strip().lower()
        if not termo:
            return None

        for label, est_id in self.label_para_id.items():
            if termo in label.lower():
                return est_id
        return None

    def calcular(self):
        origem_txt = self.cb_origem.get()
        destino_txt = self.cb_destino.get()
        algoritmo = self.cb_algoritmo.get()

        id_origem = self._obter_id_estacao(origem_txt)
        id_destino = self._obter_id_estacao(destino_txt)

        if not id_origem or not id_destino:
            messagebox.showwarning("Atencao", "Selecione origem e destino validos.")
            return

        if id_origem == id_destino:
            messagebox.showwarning("Atencao", "Origem e destino nao podem ser iguais.")
            return

        self._escrever("-" * 70)
        self._escrever(f"Origem: {self.info[id_origem][0]} (Linha {self.info[id_origem][3]})")
        self._escrever(f"Destino: {self.info[id_destino][0]} (Linha {self.info[id_destino][3]})")
        self._escrever(f"Algoritmo: {algoritmo}")

        if algoritmo == "Dijkstra":
            tempo, caminho = dijkstra(self.grafo, id_origem, id_destino)
            if caminho is None:
                self._escrever("Rota nao encontrada.\n")
                return

            self._escrever(f"Tempo estimado: {tempo // 60} min {tempo % 60} seg")
            self._escrever(f"Estacoes no caminho: {len(caminho)}")
            self._escrever("Gerando mapa: rota_metro_dijkstra.html")
            gerar_mapa(
                self.grafo,
                self.coords,
                self.linha_estacao,
                self.info,
                self.linhas_estacoes,
                caminho,
                nome_arquivo="rota_metro_dijkstra.html",
            )
            self._escrever("Mapa aberto no navegador.\n")

        elif algoritmo == "BFS":
            caminho = bfs_menor_estacoes(self.grafo, id_origem, id_destino)
            if caminho is None:
                self._escrever("Rota nao encontrada.\n")
                return

            tempo = calcular_tempo_caminho(self.grafo, caminho)
            self._escrever(f"Menor numero de trechos: {len(caminho) - 1}")
            self._escrever(f"Estacoes no caminho: {len(caminho)}")
            if tempo is not None:
                self._escrever(f"Tempo desse caminho BFS: {tempo // 60} min {tempo % 60} seg")
            self._escrever("Gerando mapa: rota_metro_bfs.html")
            gerar_mapa(
                self.grafo,
                self.coords,
                self.linha_estacao,
                self.info,
                self.linhas_estacoes,
                caminho,
                nome_arquivo="rota_metro_bfs.html",
            )
            self._escrever("Mapa aberto no navegador.\n")

        else:
            tempo_dij, caminho_dij = dijkstra(self.grafo, id_origem, id_destino)
            caminho_bfs = bfs_menor_estacoes(self.grafo, id_origem, id_destino)

            if caminho_dij is None or caminho_bfs is None:
                self._escrever("Rota nao encontrada em um dos algoritmos.\n")
                return

            tempo_bfs = calcular_tempo_caminho(self.grafo, caminho_bfs)

            self._escrever("[DIJKSTRA]")
            self._escrever(f"Tempo: {tempo_dij // 60} min {tempo_dij % 60} seg")
            self._escrever(f"Trechos: {len(caminho_dij) - 1}")

            self._escrever("[BFS]")
            self._escrever(f"Trechos: {len(caminho_bfs) - 1}")
            if tempo_bfs is not None:
                self._escrever(f"Tempo: {tempo_bfs // 60} min {tempo_bfs % 60} seg")
                diff = tempo_bfs - tempo_dij
                if diff > 0:
                    self._escrever(f"Dijkstra foi {diff // 60} min {diff % 60} seg mais rapido.")
                elif diff < 0:
                    d = abs(diff)
                    self._escrever(f"BFS foi {d // 60} min {d % 60} seg mais rapido (verifique dados).")
                else:
                    self._escrever("Empate de tempo.")

            self._escrever("Gerando mapas: rota_metro_dijkstra.html e rota_metro_bfs.html")
            gerar_mapa(
                self.grafo,
                self.coords,
                self.linha_estacao,
                self.info,
                self.linhas_estacoes,
                caminho_dij,
                nome_arquivo="rota_metro_dijkstra.html",
            )
            gerar_mapa(
                self.grafo,
                self.coords,
                self.linha_estacao,
                self.info,
                self.linhas_estacoes,
                caminho_bfs,
                nome_arquivo="rota_metro_bfs.html",
            )
            self._escrever("Mapas abertos no navegador.\n")

    def limpar(self):
        self.txt_saida.delete("1.0", "end")


def main():
    root = tk.Tk()
    MetroApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
