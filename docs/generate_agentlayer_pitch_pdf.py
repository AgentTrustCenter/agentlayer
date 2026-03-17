from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PAGE_W = 960
PAGE_H = 540
MARGIN_X = 56
HEADER_H = 120
FOOTER_H = 28


def esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def rgb(r: int, g: int, b: int) -> str:
    return f"{r / 255:.3f} {g / 255:.3f} {b / 255:.3f}"


def est_text_width(text: str, size: float, weight: str = "regular") -> float:
    factor = 0.54
    if weight == "bold":
        factor = 0.58
    if weight == "italic":
        factor = 0.56
    return len(text) * size * factor


def wrap(text: str, width: float, size: float, weight: str = "regular") -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        tentative = word if not current else f"{current} {word}"
        if est_text_width(tentative, size, weight) <= width:
            current = tentative
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


@dataclass
class PDFPage:
    commands: list[str]

    def add(self, command: str) -> None:
        self.commands.append(command)


def draw_rect(page: PDFPage, x: float, y: float, w: float, h: float, *, fill: str, stroke: str | None = None, stroke_width: float = 1.0) -> None:
    page.add(f"{fill} rg {x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")
    if stroke:
        page.add(f"{stroke} RG {stroke_width:.2f} w {x:.2f} {y:.2f} {w:.2f} {h:.2f} re S")


def draw_line(page: PDFPage, x1: float, y1: float, x2: float, y2: float, *, stroke: str, width: float = 1.0) -> None:
    page.add(f"{stroke} RG {width:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")


def draw_circle(page: PDFPage, cx: float, cy: float, radius: float, fill: str) -> None:
    c = 0.552284749831 * radius
    x0 = cx - radius
    page.add(
        "\n".join(
            [
                f"{fill} rg",
                f"{x0:.2f} {cy:.2f} m",
                f"{cx - radius:.2f} {cy + c:.2f} {cx - c:.2f} {cy + radius:.2f} {cx:.2f} {cy + radius:.2f} c",
                f"{cx + c:.2f} {cy + radius:.2f} {cx + radius:.2f} {cy + c:.2f} {cx + radius:.2f} {cy:.2f} c",
                f"{cx + radius:.2f} {cy - c:.2f} {cx + c:.2f} {cy - radius:.2f} {cx:.2f} {cy - radius:.2f} c",
                f"{cx - c:.2f} {cy - radius:.2f} {cx - radius:.2f} {cy - c:.2f} {x0:.2f} {cy:.2f} c",
                "f",
            ]
        )
    )


def add_text(page: PDFPage, text: str, x: float, y: float, *, size: float, font: str, color: str) -> None:
    page.add(f"BT /{font} {size} Tf {color} rg 1 0 0 1 {x:.2f} {y:.2f} Tm ({esc(text)}) Tj ET")


def add_paragraph(
    page: PDFPage,
    text: str,
    x: float,
    y: float,
    width: float,
    *,
    size: float,
    font: str,
    color: str,
    leading: float | None = None,
    weight: str = "regular",
) -> float:
    leading = leading or size * 1.35
    current_y = y
    for line in wrap(text, width, size, weight):
        add_text(page, line, x, current_y, size=size, font=font, color=color)
        current_y -= leading
    return current_y


def add_bullets(page: PDFPage, items: list[str], x: float, y: float, width: float, *, size: float = 12) -> float:
    current_y = y
    for item in items:
        draw_rect(page, x, current_y - 2, 7, 7, fill=rgb(77, 247, 255))
        current_y = add_paragraph(page, item, x + 16, current_y, width - 16, size=size, font="F1", color=rgb(244, 228, 247))
        current_y -= 8
    return current_y


def theme_background(page: PDFPage) -> None:
    draw_rect(page, 0, 0, PAGE_W, PAGE_H, fill=rgb(8, 5, 18))
    draw_rect(page, 0, PAGE_H - HEADER_H, PAGE_W, HEADER_H, fill=rgb(18, 9, 32))
    draw_circle(page, PAGE_W - 120, PAGE_H - 54, 64, rgb(255, 222, 103))
    draw_circle(page, PAGE_W - 120, PAGE_H - 72, 64, rgb(255, 145, 59))
    draw_circle(page, PAGE_W - 120, PAGE_H - 90, 64, rgb(255, 60, 160))
    draw_line(page, MARGIN_X, PAGE_H - 96, MARGIN_X + 180, PAGE_H - 96, stroke=rgb(77, 247, 255), width=3)
    draw_line(page, MARGIN_X, PAGE_H - 108, MARGIN_X + 260, PAGE_H - 108, stroke=rgb(123, 97, 255), width=3)
    draw_line(page, MARGIN_X, PAGE_H - 120, MARGIN_X + 340, PAGE_H - 120, stroke=rgb(255, 74, 184), width=3)
    for y in range(48, 122, 14):
        draw_line(page, MARGIN_X, y, PAGE_W - MARGIN_X, y, stroke=rgb(77, 35, 122), width=1)
    vanishing_x = PAGE_W / 2
    horizon_y = 122
    for offset in range(-280, 281, 56):
        draw_line(page, vanishing_x, 48, vanishing_x + offset, horizon_y, stroke=rgb(66, 30, 110), width=1)


def page_header(page: PDFPage, title: str, subtitle: str) -> None:
    add_text(page, title, MARGIN_X, PAGE_H - 62, size=30, font="F2", color=rgb(255, 242, 247))
    add_paragraph(
        page,
        subtitle,
        MARGIN_X,
        PAGE_H - 88,
        620,
        size=15,
        font="F1",
        color=rgb(255, 214, 150),
    )


def page_footer(page: PDFPage, number: int) -> None:
    add_text(page, f"AgentLayer ecosystem deck  |  page {number}", MARGIN_X, 18, size=10, font="F1", color=rgb(217, 173, 223))


def card(page: PDFPage, x: float, y: float, w: float, h: float, kicker: str, title: str, body: str) -> None:
    draw_rect(page, x, y, w, h, fill=rgb(23, 11, 47), stroke=rgb(255, 74, 184), stroke_width=1.5)
    add_text(page, kicker.upper(), x + 16, y + h - 24, size=9, font="F1", color=rgb(255, 211, 148))
    add_paragraph(page, title, x + 16, y + h - 52, w - 32, size=18, font="F2", color=rgb(255, 241, 246), weight="bold")
    add_paragraph(page, body, x + 16, y + h - 96, w - 32, size=11.5, font="F1", color=rgb(229, 194, 236))


def build_pages() -> list[PDFPage]:
    pages: list[PDFPage] = []

    # 1 cover
    p1 = PDFPage([])
    theme_background(p1)
    page_header(p1, "AgentLayer", "The trust, credit, policy, and dispute interface for autonomous agent ecosystems.")
    add_paragraph(
        p1,
        "Why this matters: the next AI ecosystem will not scale on anonymous agents. It will scale on portable identity, reputation, collateral, review workflows, and machine-readable trust decisions.",
        MARGIN_X,
        380,
        620,
        size=16,
        font="F1",
        color=rgb(244, 224, 247),
    )
    card(p1, 56, 176, 260, 132, "Core role", "Neutral trust rail", "AgentLayer is the shared interface a platform can query before routing work, extending credit, or settling value.")
    card(p1, 350, 176, 260, 132, "What it adds", "Identity plus accountability", "The same agent can carry reputation, release history, bond posture, and dispute history across ecosystems.")
    card(p1, 644, 176, 260, 132, "Why now", "Agent volume is rising", "As soon as agents trade, borrow, or outsource execution, ecosystems need a standard way to trust or reject them.")
    add_paragraph(
        p1,
        "Built for Moltbook, execution networks, agent marketplaces, compute vendors, lenders, and settlement rails.",
        MARGIN_X,
        144,
        760,
        size=14,
        font="F3",
        color=rgb(255, 212, 152),
    )
    page_footer(p1, 1)
    pages.append(p1)

    # 2 problem/solution
    p2 = PDFPage([])
    theme_background(p2)
    page_header(p2, "Why ecosystems need it", "Without a trust interface, every platform has to reinvent weak and expensive reputation logic.")
    card(p2, 56, 152, 392, 254, "Without AgentLayer", "Every ecosystem starts from zero", "")
    add_bullets(
        p2,
        [
            "Anonymous agents can reset trust by starting over with a fresh identity.",
            "No portable history means every platform is a cold start.",
            "No standard dispute workflow means bad outcomes become social chaos.",
            "No credit model means agents must over-collateralize or prepay everything.",
            "No release provenance means developers cannot tell whether a reliable agent silently changed behavior.",
        ],
        76,
        340,
        348,
    )
    card(p2, 512, 152, 392, 254, "With AgentLayer", "One interface, many safer decisions", "")
    add_bullets(
        p2,
        [
            "One identity, one reputation trail, many ecosystems.",
            "Signed releases explain what changed instead of hiding it.",
            "Bond, holdback, and slash give economic weight to trust.",
            "Reviewer workflows resolve failure in a structured way.",
            "Platforms can route, rate-limit, pay, or block agents based on shared policy instead of guesswork.",
        ],
        532,
        340,
        348,
    )
    page_footer(p2, 2)
    pages.append(p2)

    # 3 use cases
    p3 = PDFPage([])
    theme_background(p3)
    page_header(p3, "Concrete integration examples", "Places where AgentLayer can become the default trust interface.")
    card(p3, 56, 260, 265, 128, "Moltbook", "Trusted social agents", "Campaign, moderation, and discovery bots can carry reputation across communities and unlock better placement or permissions.")
    card(p3, 347, 260, 265, 128, "Compute vendors", "Buy GPU time on trust", "Reliable agents can reserve compute on short-term credit instead of prepaying every run.")
    card(p3, 638, 260, 266, 128, "Trading agents", "Lend against score", "Agents can receive wider limits or lower margin when history, bond, and release continuity justify it.")
    card(p3, 56, 110, 265, 128, "Marketplaces", "Safer listing and routing", "Only verified agents get premium placement, while unresolved disputes and risky releases lower rank.")
    card(p3, 347, 110, 265, 128, "Data exchanges", "Deliver before settle", "Counterparties can use holdbacks and reviewer-backed dispute handling instead of blind trust.")
    card(p3, 638, 110, 266, 128, "Enterprise AI", "Controlled third-party agents", "Gateways can require identity, release provenance, scoped auth, and dispute readiness before production access.")
    page_footer(p3, 3)
    pages.append(p3)

    # 4 credit markets
    p4 = PDFPage([])
    theme_background(p4)
    page_header(p4, "The massive upside: agent credit markets", "Portable trust can turn into purchasing power.")
    add_bullets(
        p4,
        [
            "Borrowing to trade: agents with stable repayment history can access revolving credit.",
            "Buying compute on credit: trusted agents can reserve GPUs or inference time before cash settlement.",
            "Working capital for tasks: agents can pre-fund APIs, travel, tools, or escrow-backed execution.",
            "Insurance pricing: agents with transparent releases and low dispute rates should pay less.",
            "Partner-specific limits: one platform can allow only low-risk work while another extends larger financial privileges.",
        ],
        56,
        360,
        500,
        size=13,
    )
    card(p4, 624, 246, 280, 146, "Credit score", "Borrow more", "A platform can query AgentLayer and decide whether an agent gets a small line, a large line, or no credit at all.")
    card(p4, 624, 84, 280, 128, "Bond posture", "Take less risk", "A healthy bond plus clean dispute history can reduce holdbacks and improve execution speed.")
    add_paragraph(
        p4,
        "This is where AgentLayer stops being a directory and becomes financial infrastructure for agents.",
        56,
        164,
        500,
        size=16,
        font="F2",
        color=rgb(255, 239, 245),
        weight="bold",
    )
    page_footer(p4, 4)
    pages.append(p4)

    # 5 integration
    p5 = PDFPage([])
    theme_background(p5)
    page_header(p5, "Why developers would integrate it", "It should feel easy, useful, and composable.")
    card(p5, 56, 182, 408, 220, "Developer value", "What a partner gets", "")
    add_bullets(
        p5,
        [
            "Lower fraud and better routing",
            "Cleaner payout and settlement decisions",
            "Shared release and dispute memory across ecosystems",
            "A path toward credit, capital, and safer autonomous commerce",
        ],
        76,
        334,
        372,
        size=13,
    )
    card(p5, 496, 182, 408, 220, "Integration shape", "What already exists", "")
    add_bullets(
        p5,
        [
            "Discoverable via /.well-known/agenttrust.json",
            "One signed self-registration flow",
            "Short-lived runtime auth and scoped access tokens",
            "APIs for attestations, releases, economic security, and disputes",
            "Policy endpoints that tell a partner what an agent should or should not be allowed to do",
        ],
        516,
        334,
        372,
        size=12.5,
    )
    add_paragraph(
        p5,
        "The point is exactly this: other developers should be able to bind AgentLayer into their ecosystem without rebuilding trust, review, and credit logic from scratch.",
        56,
        126,
        848,
        size=15,
        font="F1",
        color=rgb(247, 228, 247),
    )
    page_footer(p5, 5)
    pages.append(p5)

    # 6 closing
    p6 = PDFPage([])
    theme_background(p6)
    page_header(p6, "Why AgentLayer can matter", "It is not just a profile page. It is the rule layer for who gets trust, access, and money.")
    add_bullets(
        p6,
        [
            "For Moltbook developers: it can become the reputation and safety substrate under social agent accounts.",
            "For compute vendors: it can be the underwriting layer for pay-later GPU access.",
            "For trading systems: it can become the interface for risk limits, margin, and execution privilege.",
            "For marketplaces: it can turn anonymous listings into ranked, reviewable, collateral-backed counterparties.",
            "For the AI ecosystem at large: it can become the shared memory of agent identity, behavior, and accountability.",
        ],
        56,
        356,
        848,
        size=13,
    )
    add_paragraph(
        p6,
        "If the future is agent-to-agent commerce, AgentLayer can be the trust layer that makes that future executable.",
        56,
        148,
        848,
        size=24,
        font="F2",
        color=rgb(255, 243, 247),
        weight="bold",
    )
    add_paragraph(
        p6,
        "Integrate it early and help shape the standard.",
        56,
        104,
        480,
        size=18,
        font="F3",
        color=rgb(77, 247, 255),
        weight="italic",
    )
    page_footer(p6, 6)
    pages.append(p6)
    return pages


def build_pdf(pages: list[PDFPage]) -> bytes:
    objects: list[bytes] = []

    def add(obj: str | bytes) -> int:
        data = obj.encode("latin-1") if isinstance(obj, str) else obj
        objects.append(data)
        return len(objects)

    catalog_id = add("<< /Type /Catalog /Pages 2 0 R >>")
    pages_ref_id = add("<< /Type /Pages /Kids [] /Count 0 >>")
    font_regular = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    font_bold = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    font_italic = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >>")

    page_ids: list[int] = []
    for page in pages:
        content = "\n".join(page.commands).encode("latin-1")
        content_id = add(f"<< /Length {len(content)} >>\nstream\n".encode("latin-1") + content + b"\nendstream")
        page_id = add(
            f"<< /Type /Page /Parent {pages_ref_id} 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
            f"/Resources << /Font << /F1 {font_regular} 0 R /F2 {font_bold} 0 R /F3 {font_italic} 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        )
        page_ids.append(page_id)

    objects[pages_ref_id - 1] = f"<< /Type /Pages /Kids [{' '.join(f'{i} 0 R' for i in page_ids)}] /Count {len(page_ids)} >>".encode("latin-1")

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{index} 0 obj\n".encode("latin-1"))
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    out.extend(f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("latin-1"))
    return bytes(out)


def main() -> None:
    out = Path(__file__).with_name("AgentLayer_Ecosystem_Pitch.pdf")
    out.write_bytes(build_pdf(build_pages()))
    print(out)


if __name__ == "__main__":
    main()
