"""Build the Muster architecture diagrams as one draw.io file, two pages.

Generated rather than hand-drawn, so the geometry can be iterated on and the
shapes stay in step with what the code does.

Two pages on purpose. A single diagram carrying both the layering and the
decision path produced edges spanning the whole canvas, crossing every box
between their ends; the picture was busy without being informative. So:

  1. "How it works" - the whole idea in ten big shapes. Someone should be able
     to read it once, at a glance, without following a line back.
  2. "Under the hood" - the same story with the machinery named: the two
     interventions, the snapshot, and the two places a human is asked.

    python build_architecture.py    ->  muster-architecture.drawio
"""

from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).parent
OUT = HERE / "muster-architecture.drawio"

INK, MUTED, LINE, ACCENT = "#161a25", "#5a6273", "#c9cede", "#4429c4"

GROUP = ("rounded=1;whiteSpace=wrap;html=1;fillColor=#f7f8fa;strokeColor=#e3e6ec;"
         "verticalAlign=top;align=left;spacingLeft=14;spacingTop=6;fontSize=12;"
         f"fontStyle=1;fontColor={MUTED};arcSize=4;")
NODE = (f"rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor={LINE};"
        f"fontSize=11;fontColor={INK};arcSize=14;spacing=6;")
ACC = ("rounded=1;whiteSpace=wrap;html=1;fillColor=#efeaff;strokeColor=#4429c4;"
       "fontSize=11;fontColor=#2f1b7a;arcSize=14;spacing=6;")
STOP = ("rounded=1;whiteSpace=wrap;html=1;fillColor=#fdeceb;strokeColor=#b42318;"
        "fontSize=11;fontColor=#912018;arcSize=14;spacing=6;")
OK = ("rounded=1;whiteSpace=wrap;html=1;fillColor=#eefaf3;strokeColor=#12734a;"
      "fontSize=11;fontColor=#0d5c3a;arcSize=14;spacing=6;")
ACTOR = (f"ellipse;whiteSpace=wrap;html=1;fillColor={ACCENT};strokeColor=#2f1b7a;"
         "fontSize=11;fontColor=#ffffff;fontStyle=1;")
NOTE = ("text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize=10;"
        f"fontColor={MUTED};")
TITLE = ("text;html=1;whiteSpace=wrap;align=left;verticalAlign=middle;fontSize=18;"
         f"fontStyle=1;fontColor={INK};")

EDGE = ("edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;jettySize=auto;"
        f"strokeColor={MUTED};fontSize=10;fontColor={MUTED};endArrow=blockThin;"
        "endFill=1;labelBackgroundColor=#ffffff;")
EDGE_ACC = ("edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;jettySize=auto;"
            f"strokeColor={ACCENT};strokeWidth=2;fontSize=10;fontColor={ACCENT};"
            "endArrow=blockThin;endFill=1;labelBackgroundColor=#ffffff;fontStyle=1;")
EDGE_STOP = ("edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;jettySize=auto;"
             "strokeColor=#b42318;fontSize=10;fontColor=#b42318;endArrow=blockThin;"
             "endFill=1;dashed=1;labelBackgroundColor=#ffffff;")


class Page:
    def __init__(self, name: str, w: int, h: int) -> None:
        self.name, self.w, self.h, self.cells = name, w, h, []

    def node(self, ident, label, x, y, w, h, style=NODE):
        # html=1 means the label is markup, so a newline has to be a line break
        # tag - and the tag itself lives inside an XML attribute, so it has to be
        # entity-escaped. Writing a bare <br> made the file invalid XML from the
        # first multi-line label onwards, and draw.io silently rendered only the
        # cells before it.
        value = escape(label).replace("\n", "&lt;br&gt;")
        self.cells.append(
            f'<mxCell id="{ident}" value="{value}" style="{style}" vertex="1" '
            f'parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" '
            'as="geometry"/></mxCell>'
        )

    def edge(self, ident, src, dst, label="", style=EDGE, exit=None, entry=None):
        s = style
        if exit:
            s += f"exitX={exit[0]};exitY={exit[1]};exitDx=0;exitDy=0;"
        if entry:
            s += f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;"
        self.cells.append(
            f'<mxCell id="{ident}" value="{escape(label)}" style="{s}" edge="1" '
            f'parent="1" source="{src}" target="{dst}">'
            '<mxGeometry relative="1" as="geometry"/></mxCell>'
        )

    def xml(self, ident):
        return (
            f'  <diagram id="{ident}" name="{escape(self.name)}">\n'
            f'    <mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" guides="1" '
            f'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
            f'pageWidth="{self.w}" pageHeight="{self.h}" math="0" shadow="0">\n'
            '      <root>\n        <mxCell id="0"/>\n        <mxCell id="1" parent="0"/>\n'
            + "\n".join("        " + c for c in self.cells) + "\n"
            '      </root>\n    </mxGraphModel>\n  </diagram>\n'
        )


# ============================ page 1: how it works ==========================
# Big shapes, few words, one direction. A judge should get the whole idea from
# this page without reading anything twice; the detail lives on page two for
# anyone who wants it.

BIG = ("rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#c9cede;"
       "fontSize=15;fontColor=#161a25;arcSize=12;spacing=10;")
BIG_ACC = ("rounded=1;whiteSpace=wrap;html=1;fillColor=#efeaff;strokeColor=#4429c4;"
           "strokeWidth=2;fontSize=15;fontColor=#2f1b7a;arcSize=12;spacing=10;")
BIG_OK = ("rounded=1;whiteSpace=wrap;html=1;fillColor=#eefaf3;strokeColor=#12734a;"
          "strokeWidth=2;fontSize=15;fontColor=#0d5c3a;arcSize=12;spacing=10;")
BIG_ACTOR = ("ellipse;whiteSpace=wrap;html=1;fillColor=#4429c4;strokeColor=#2f1b7a;"
             "fontSize=15;fontColor=#ffffff;fontStyle=1;")
SUB = ("text;html=1;whiteSpace=wrap;align=center;verticalAlign=top;fontSize=12;"
       "fontColor=#5a6273;")
BIG_EDGE = ("edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeColor=#5a6273;"
            "strokeWidth=2;fontSize=13;fontColor=#5a6273;endArrow=blockThin;endFill=1;"
            "labelBackgroundColor=#ffffff;")
BIG_EDGE_ACC = BIG_EDGE.replace("#5a6273", "#4429c4") + "fontStyle=1;"

a = Page("How it works", 1340, 760)
a.node("t", "Muster — an autonomous shift coordinator that knows the law", 60, 34, 900, 34, TITLE)
a.node("tsub", "A shift loses its worker. Four cities price that differently. Muster does the "
               "arithmetic, and stops at the line it may not cross.", 60, 68, 900, 24, SUB.replace("align=center", "align=left"))

a.node("s1", "A shift loses\nits worker", 60, 200, 160, 90, BIG_ACTOR)
a.node("s2", "Muster finds every\nlawful cover and\nprices each one", 280, 195, 200, 100, BIG)
a.node("s3", "The law\n4 city rulebooks, as data", 280, 360, 200, 70, BIG_ACC)
a.node("s4", "Is it inside the\nlimits you set?", 550, 200, 180, 90, BIG_ACC)

a.node("o1", "Yes — it does it\nand writes a receipt", 820, 100, 230, 80, BIG_OK)
a.node("o2", "No — it asks you\ncost, overtime, hours", 820, 205, 230, 80, BIG)
a.node("o3", "Only the worker can say yes\na rest-period waiver", 820, 310, 230, 80, BIG_ACC)

a.node("p1", "Operator", 1130, 210, 150, 70, BIG_ACTOR)
a.node("p2", "Worker", 1130, 315, 150, 70, BIG_ACTOR)
a.node("r1", "Receipt\nthe clause, the money,\nwho decided", 1130, 95, 150, 90, BIG_OK)

a.node("k1", "Every figure comes from the city's own .gov page.", 270, 438, 220, 40, SUB)
a.node("k2", "Two rules no setting can move: Muster never waives a worker's rest period on "
             "their behalf, and never asks someone who has already said no.",
       550, 478, 420, 44, SUB.replace("align=center", "align=left"))
a.node("k3", "Nothing is committed before it stops — a held decision leaves the receipts empty.",
       990, 478, 300, 44, SUB.replace("align=center", "align=left"))

a.node("g8", "BUILT WITH", 60, 560, 1180, 130, GROUP)
a.node("d1", "Strands Agents\ntwo loops, and the autonomy\nboundary as executable code", 84, 596, 270, 72, BIG_ACC)
a.node("d2", "Amazon Bedrock\nClaude Sonnet reasons.\nIt never does the arithmetic.", 374, 596, 270, 72, BIG_ACC)
a.node("d3", "AWS App Runner\none container: agent,\nAPI and console", 664, 596, 250, 72, BIG)
a.node("d4", "An MCP server\nread-only over the same\nengine. It cannot change a week.", 934, 596, 280, 72, BIG)

a.edge("a1", "s1", "s2", "", BIG_EDGE)
a.edge("a2", "s3", "s2", "prices from", BIG_EDGE)
a.edge("a3", "s2", "s4", "", BIG_EDGE)
# Fan out from three different points on the same edge of the question, so no
# branch has to cross the box belonging to another branch.
a.edge("a4", "s4", "o1", "", BIG_EDGE_ACC, exit=(1, 0.2), entry=(0, 0.5))
a.edge("a5", "s4", "o2", "", BIG_EDGE, exit=(1, 0.5), entry=(0, 0.5))
a.edge("a6", "s4", "o3", "", BIG_EDGE_ACC, exit=(1, 0.8), entry=(0, 0.5))
a.edge("a7", "o1", "r1", "", BIG_EDGE_ACC, exit=(1, 0.5), entry=(0, 0.5))
a.edge("a8", "o2", "p1", "", BIG_EDGE, exit=(1, 0.5), entry=(0, 0.5))
a.edge("a9", "o3", "p2", "", BIG_EDGE_ACC, exit=(1, 0.5), entry=(0, 0.5))
a.edge("a10", "p1", "r1", "approve", BIG_EDGE_ACC, exit=(0.5, 0), entry=(0.5, 1))
a.edge("a11", "p2", "s4", "yes", BIG_EDGE_ACC, exit=(0.5, 1), entry=(0.5, 1))

# ========================= page 2: the decision path ========================
b = Page("Under the hood", 1560, 800)
b.node("t2", "One guarded tool call, end to end", 40, 24, 700, 30, TITLE)
b.node("n0", "The two places a person is asked, and why they are different people.",
       40, 54, 700, 20, NOTE)

b.node("d_in", "A shift loses\nits worker", 40, 130, 120, 56, ACTOR)
b.node("d_hold", "HOLD loop\nlists every lawful cover,\neach priced from the\ngoverning ordinance", 200, 118, 170, 80)
b.node("d_prop", "proposes\nassign_cover", 410, 132, 120, 52, ACC)

b.node("d_g1", "1 · PostingDependencyGuard\nis this week posted, and is\nthere an approved cover behind it?", 570, 112, 210, 72)
b.node("d_deny", "Deny\nnever reaches the world", 820, 118, 150, 60, STOP)
b.node("d_g2", "2 · EscalationPolicy\nmay it act alone at\nthis autonomy level?", 570, 240, 210, 72, ACC)

b.node("d_ok", "Proceed\nwithin limits", 820, 246, 150, 60, OK)
b.node("d_commit", "Commit + receipt\nclause · money · carve-out\nconsent · who decided", 1010, 236, 190, 80, OK)

b.node("d_conf", "Confirm\nsnapshot the run and stop", 570, 372, 210, 56, ACC)
b.node("d_inbox", "Decision inbox\nthe question, and the\nwhole agent state", 570, 456, 210, 66)
b.node("d_op", "Operator", 610, 560, 130, 50, ACTOR)
b.node("d_appr", "Approve\nthe same run resumes, hours later,\non another machine", 820, 540, 200, 72, OK)
b.node("d_decl", "Decline\nnothing is handed back to the agent;\nthe shift stays open", 820, 640, 200, 72, STOP)

b.node("d_rest", "requires a rest-period waiver", 200, 300, 170, 34, ACC)
b.node("d_ask", "request_consent\nthe ask, never the waiver", 200, 350, 170, 50, ACC)
b.node("d_worker", "Worker", 44, 452, 110, 50, ACTOR)
b.node("d_yes", "Yes\nthe waiver is satisfied;\nwhat is left is the money", 200, 428, 170, 62, OK)
b.node("d_no", "No\nfinal — Muster asks\nsomeone else, never her again", 200, 508, 170, 62, STOP)

b.node("d_note1", "Two rules fire at every autonomy level, the most permissive included: "
                  "Muster will never waive a worker's rest period on their behalf, and never "
                  "asks someone who has already declined. Oregon requires the worker's own "
                  "consent, NYC requires it in writing, and Chicago's guidance says the Right "
                  "to Rest has no exceptions. An agent that could dial past those would not be "
                  "more capable — it would be unlawful.",
       1250, 100, 280, 130, NOTE)
b.node("d_note2", "Nothing is committed before the pause. A held decision leaves Receipts "
                  "empty — it stopped before it did anything, not after.",
       1250, 250, 280, 60, NOTE)

b.edge("b1", "d_in", "d_hold", "")
b.edge("b2", "d_hold", "d_prop", "cheapest lawful")
b.edge("b3", "d_prop", "d_g1", "")
b.edge("b4", "d_g1", "d_deny", "Deny", EDGE_STOP)
b.edge("b5", "d_g1", "d_g2", "Proceed")
b.edge("b6", "d_g2", "d_ok", "no rule fires")
b.edge("b7", "d_ok", "d_commit", "")
b.edge("b8", "d_g2", "d_conf", "a rule fires", EDGE_ACC)
b.edge("b9", "d_conf", "d_inbox", "", EDGE_ACC)
b.edge("b10", "d_inbox", "d_op", "surfaced on Decisions")
b.edge("b11", "d_op", "d_appr", "", EDGE_ACC)
b.edge("b12", "d_op", "d_decl", "", EDGE_STOP, exit=(0.5, 1), entry=(0, 0.5))
b.edge("b13", "d_appr", "d_commit", "resumes the same run", EDGE_ACC,
       exit=(1, 0.5), entry=(0.5, 1))
b.edge("b14", "d_hold", "d_rest", "if every option", EDGE_ACC)
b.edge("b15", "d_rest", "d_ask", "", EDGE_ACC)
b.edge("b16", "d_ask", "d_worker", "asks", EDGE_ACC, exit=(0, 0.5), entry=(0.5, 0))
b.edge("b17", "d_worker", "d_yes", "yes", EDGE_ACC, exit=(1, 0.5), entry=(0, 0.5))
b.edge("b18", "d_worker", "d_no", "no", EDGE_STOP, exit=(0.5, 1), entry=(0, 0.5))
b.edge("b19", "d_yes", "d_prop", "back into the chain", EDGE_ACC,
       exit=(1, 0.5), entry=(0, 1))

XML = ('<mxfile host="app.diagrams.net" type="device">\n'
       + a.xml("how-it-works") + b.xml("under-the-hood")
       + '</mxfile>\n')
OUT.write_text(XML, encoding="utf-8")
print(f"wrote {OUT}  ({len(a.cells)} + {len(b.cells)} cells)")
