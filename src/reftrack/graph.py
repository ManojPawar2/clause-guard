"""Citation graph rendering (pyvis) for the References tab (polish tier)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(Path(__file__).parent))
from citations import build_citation_graph, load_corpus  # noqa: E402


def render_html(corpus=None, out_path=None, highlight=None) -> str:
    """Build the corpus citation graph; return HTML string for st.components."""
    from pyvis.network import Network

    corpus = corpus or load_corpus()
    edges = build_citation_graph(corpus)
    meta = {r["gr_code"]: r for r in corpus}
    nodes = {c for e in edges for c in e}

    palette = {}
    net = Network(height="520px", width="100%", directed=True, bgcolor="#ffffff")
    colors = ["#e63946", "#457b9d", "#2a9d8f", "#f4a261", "#8d5a97"]
    for n in nodes:
        dept = (meta.get(n, {}).get("department") or "?")[:40]
        if dept not in palette:
            palette[dept] = colors[len(palette) % len(colors)]
        net.add_node(
            n, label=n[-8:], color="#ffd60a" if n == highlight else palette[dept],
            title=f"{n}\n{dept}\n{(meta.get(n, {}).get('subject') or '')[:120]}",
        )
    for a, b in edges:
        net.add_edge(a, b)
    net.repulsion(node_distance=120, spring_length=140)
    html = net.generate_html()
    if out_path:
        Path(out_path).write_text(html, encoding="utf-8")
    return html
