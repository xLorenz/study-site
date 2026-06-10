from manim import *

class TeoriaInformacion(Scene):
    def construct(self):
        self.camera.background_color = "#0a0a0f"

        # ===== SLIDE 1: Título =====
        title = Text("Teoría de la Información", font_size=44, color=BLUE, font="Menlo")
        subtitle = Text("Claude Shannon, 1948", font_size=24, color=GREY_B, font="Menlo")
        subtitle.next_to(title, DOWN, buff=0.5)
        self.play(Write(title), run_time=1.5)
        self.play(FadeIn(subtitle, shift=UP * 0.3), run_time=0.8)
        self.wait(1.2)
        self.play(FadeOut(Group(title, subtitle)))
        self.wait(0.3)

        # ===== SLIDE 2: Modelo de comunicaciones =====
        model_title = Text("Modelo de Comunicaciones", font_size=36, color=BLUE, font="Menlo")
        model_title.to_edge(UP, buff=0.5)

        boxes_labels = ["Fuente", "Transmisor", "Canal", "Receptor", "Destino"]
        boxes_colors = [GREEN, BLUE, YELLOW, BLUE, GREEN]
        boxes = VGroup()
        for label, col in zip(boxes_labels, boxes_colors):
            b = Rectangle(width=1.8, height=0.9, color=col, fill_opacity=0.15, fill_color=col)
            t = Text(label, font_size=16, color=WHITE, font="Menlo")
            t.move_to(b.get_center())
            boxes.add(VGroup(b, t))

        boxes.arrange(RIGHT, buff=0.8)
        boxes.shift(DOWN * 0.3)

        # Arrows between boxes
        arrows = VGroup()
        for i in range(len(boxes) - 1):
            a = Arrow(
                boxes[i].get_right() + RIGHT * 0.05,
                boxes[i + 1].get_left() + LEFT * 0.05,
                buff=0.05,
                color=GREY_B,
                stroke_width=2,
                max_tip_length_to_length_ratio=0.15
            )
            arrows.add(a)

        # Noise arrow into Canal
        noise_label = Text("Ruido", font_size=18, color=RED, font="Menlo")
        noise_arrow = Arrow(
            UP * 1.2 + boxes[2].get_center(),
            boxes[2].get_top(),
            buff=0.05,
            color=RED,
            stroke_width=2,
            max_tip_length_to_length_ratio=0.15
        )
        noise_label.next_to(noise_arrow.get_start(), UP, buff=0.1)

        self.play(Write(model_title), run_time=1)
        self.play(
            LaggedStart(*[FadeIn(b, shift=RIGHT * 0.3) for b in boxes], lag_ratio=0.15),
            run_time=2
        )
        self.play(LaggedStart(*[GrowArrow(a) for a in arrows], lag_ratio=0.1), run_time=1.2)
        self.play(GrowArrow(noise_arrow), FadeIn(noise_label, shift=DOWN * 0.2), run_time=0.8)
        self.wait(1.5)
        self.play(FadeOut(Group(model_title, boxes, arrows, noise_arrow, noise_label)))
        self.wait(0.3)

        # ===== SLIDE 3: Cantidad de Información =====
        ci_title = Text("Cantidad de Información", font_size=36, color=BLUE, font="Menlo")
        ci_title.to_edge(UP, buff=0.5)

        ci_principle = Text(
            "A menor probabilidad → mayor información",
            font_size=22, color=YELLOW, font="Menlo"
        )
        ci_principle.next_to(ci_title, DOWN, buff=0.6)

        # Formula
        formula = MathTex(r"I(s) = \log_2\!\left(\frac{1}{P(s)}\right)", font_size=40, color=WHITE)
        formula.next_to(ci_principle, DOWN, buff=0.6)

        unit_text = Text("Unidad: Shannon (Sh)", font_size=20, color=GREY_B, font="Menlo")
        unit_text.next_to(formula, DOWN, buff=0.5)

        self.play(Write(ci_title), run_time=1)
        self.play(Write(ci_principle), run_time=1.2)
        self.wait(0.5)
        self.play(Write(formula), run_time=1.5)
        self.play(FadeIn(unit_text, shift=UP * 0.2), run_time=0.6)
        self.wait(1.5)
        self.play(FadeOut(Group(ci_title, ci_principle, formula, unit_text)))
        self.wait(0.3)

        # ===== SLIDE 4: Ejemplo - Dado =====
        dado_title = Text("Ejemplo: Dado de 6 caras", font_size=32, color=BLUE, font="Menlo")
        dado_title.to_edge(UP, buff=0.5)

        p_text = MathTex(r"P(4) = \frac{1}{6}", font_size=32, color=GREEN)
        p_text.shift(UP * 0.8)

        calc = MathTex(
            r"I(4) = \log_2\!\left(\frac{1}{1/6}\right) = \log_2(6) = 2{,}58 \; \text{Sh}",
            font_size=30, color=WHITE
        )
        calc.next_to(p_text, DOWN, buff=0.6)

        # Binary example below
        bin_label = Text("Fuente binaria equiprobable:", font_size=22, color=GREY_B, font="Menlo")
        bin_label.next_to(calc, DOWN, buff=0.8)

        bin_calc = MathTex(
            r"P(0)=P(1)=0{,}5 \quad\Rightarrow\quad I = \log_2(2) = 1 \; \text{Sh}",
            font_size=28, color=WHITE
        )
        bin_calc.next_to(bin_label, DOWN, buff=0.4)

        self.play(Write(dado_title), run_time=0.8)
        self.play(Write(p_text), run_time=1)
        self.play(Write(calc), run_time=1.5)
        self.wait(0.5)
        self.play(FadeIn(bin_label, shift=UP * 0.2), run_time=0.6)
        self.play(Write(bin_calc), run_time=1.2)
        self.wait(1.5)
        self.play(FadeOut(Group(dado_title, p_text, calc, bin_label, bin_calc)))
        self.wait(0.3)

        # ===== SLIDE 5: Entropía =====
        h_title = Text("Entropía (H)", font_size=36, color=BLUE, font="Menlo")
        h_title.to_edge(UP, buff=0.5)

        h_desc = Text(
            "Información promedio por símbolo",
            font_size=22, color=YELLOW, font="Menlo"
        )
        h_desc.next_to(h_title, DOWN, buff=0.5)

        # Main formula
        h_formula = MathTex(
            r"H = -\sum_{i} P(s_i) \cdot \log_2\!P(s_i)",
            font_size=38, color=WHITE
        )
        h_formula.next_to(h_desc, DOWN, buff=0.6)

        # Equiprobable case
        eq_label = Text("Caso equiprobable:", font_size=20, color=GREY_B, font="Menlo")
        eq_label.next_to(h_formula, DOWN, buff=0.7)

        eq_formula = MathTex(
            r"H = \log_2(N) \; \text{[Sh/símbolo]}",
            font_size=30, color=GREEN
        )
        eq_formula.next_to(eq_label, DOWN, buff=0.3)

        self.play(Write(h_title), run_time=1)
        self.play(Write(h_desc), run_time=1)
        self.wait(0.5)
        self.play(Write(h_formula), run_time=1.5)
        self.wait(0.5)
        self.play(FadeIn(eq_label, shift=UP * 0.2), run_time=0.5)
        self.play(Write(eq_formula), run_time=1)
        self.wait(1.5)
        self.play(FadeOut(Group(h_title, h_desc, h_formula, eq_label, eq_formula)))
        self.wait(0.3)

        # ===== SLIDE 6: Ejemplo entropía - Fuente binaria =====
        ex_title = Text("Entropía: Fuente Binaria", font_size=32, color=BLUE, font="Menlo")
        ex_title.to_edge(UP, buff=0.5)

        # Binary entropy curve sketch using a simple parametric
        axes = Axes(
            x_range=[0, 1, 0.1],
            y_range=[0, 1.1, 0.2],
            x_length=5,
            y_length=3,
            axis_config={"color": GREY_B, "stroke_width": 1.5},
            tips=False,
        ).shift(DOWN * 0.2 + LEFT * 0.5)

        x_label = MathTex("p", font_size=22, color=GREY_B).next_to(axes.x_axis, RIGHT, buff=0.1)
        y_label = MathTex("H", font_size=22, color=GREY_B).next_to(axes.y_axis, UP, buff=0.1)

        # H = -p*log2(p) - (1-p)*log2(1-p)
        curve = axes.plot(
            lambda p: -p * np.log2(p) - (1 - p) * np.log2(1 - p) if 0.001 < p < 0.999 else 0,
            color=YELLOW,
            stroke_width=3,
        )

        # Mark maximum
        max_dot = Dot(axes.c2p(0.5, 1.0), color=RED, radius=0.08)
        max_label = MathTex(r"H_{max} = 1", font_size=22, color=RED)
        max_label.next_to(max_dot, UR, buff=0.2)

        # Annotations
        ann_left = Text("Predecible", font_size=16, color=GREY_B, font="Menlo")
        ann_left.next_to(axes.c2p(0.05, 0.15), DOWN, buff=0.3)
        ann_right = Text("Predecible", font_size=16, color=GREY_B, font="Menlo")
        ann_right.next_to(axes.c2p(0.95, 0.15), DOWN, buff=0.3)
        ann_center = Text("Máx. incertidumbre", font_size=16, color=YELLOW, font="Menlo")
        ann_center.next_to(axes.c2p(0.5, 1.0), UP, buff=0.5)

        self.play(Write(ex_title), run_time=0.8)
        self.play(Create(axes), FadeIn(x_label), FadeIn(y_label), run_time=1.5)
        self.play(Create(curve), run_time=2)
        self.play(FadeIn(max_dot), Write(max_label), run_time=0.8)
        self.play(FadeIn(ann_left), FadeIn(ann_right), FadeIn(ann_center), run_time=0.8)
        self.wait(1.5)
        self.play(FadeOut(Group(
            ex_title, axes, x_label, y_label, curve,
            max_dot, max_label, ann_left, ann_right, ann_center
        )))
        self.wait(0.3)

        # ===== SLIDE 7: Propiedades de la Entropía =====
        prop_title = Text("Propiedades de la Entropía", font_size=32, color=BLUE, font="Menlo")
        prop_title.to_edge(UP, buff=0.5)

        props = VGroup(
            VGroup(
                MathTex(r"H_{max} = \log_2(N)", font_size=28, color=GREEN),
                Text("Equiprobable → entropía máxima", font_size=18, color=GREY_B, font="Menlo"),
            ).arrange(DOWN, buff=0.15, aligned_edge=LEFT),
            VGroup(
                MathTex(r"H = 0", font_size=28, color=RED),
                Text("Un símbolo seguro → sin información", font_size=18, color=GREY_B, font="Menlo"),
            ).arrange(DOWN, buff=0.15, aligned_edge=LEFT),
        ).arrange(DOWN, buff=0.8, aligned_edge=LEFT).shift(DOWN * 0.1)

        self.play(Write(prop_title), run_time=0.8)
        self.play(FadeIn(props[0], shift=RIGHT * 0.3), run_time=1)
        self.wait(0.5)
        self.play(FadeIn(props[1], shift=RIGHT * 0.3), run_time=1)
        self.wait(1.5)
        self.play(FadeOut(Group(prop_title, props)))
        self.wait(0.3)

        # ===== SLIDE 8: Tasa de Información =====
        r_title = Text("Tasa de Información (R)", font_size=36, color=BLUE, font="Menlo")
        r_title.to_edge(UP, buff=0.5)

        r_desc = Text(
            "Velocidad de producción de información",
            font_size=22, color=YELLOW, font="Menlo"
        )
        r_desc.next_to(r_title, DOWN, buff=0.5)

        r_formula = MathTex(
            r"R = \frac{H}{\tau}",
            font_size=42, color=WHITE
        )
        r_formula.next_to(r_desc, DOWN, buff=0.5)

        r_units = VGroup(
            MathTex(r"H", font_size=22, color=GREEN).set_color(GREEN),
            Text("= entropía [Sh/símbolo]", font_size=16, color=GREY_B, font="Menlo"),
        ).arrange(RIGHT, buff=0.15)

        r_units2 = VGroup(
            MathTex(r"\tau", font_size=22, color=GREEN),
            Text("= duración media [s/símbolo]", font_size=16, color=GREY_B, font="Menlo"),
        ).arrange(RIGHT, buff=0.15)

        r_units3 = VGroup(
            MathTex(r"R", font_size=22, color=GREEN),
            Text("= tasa [bps] o [Sh/s]", font_size=16, color=GREY_B, font="Menlo"),
        ).arrange(RIGHT, buff=0.15)

        r_all = VGroup(r_units, r_units2, r_units3).arrange(DOWN, buff=0.25, aligned_edge=LEFT)
        r_all.next_to(r_formula, DOWN, buff=0.5)

        self.play(Write(r_title), run_time=0.8)
        self.play(Write(r_desc), run_time=1)
        self.play(Write(r_formula), run_time=1.2)
        self.play(LaggedStart(*[FadeIn(u, shift=RIGHT * 0.3) for u in [r_units, r_units2, r_units3]], lag_ratio=0.3), run_time=1.2)
        self.wait(1.5)
        self.play(FadeOut(Group(r_title, r_desc, r_formula, r_all)))
        self.wait(0.3)

        # ===== SLIDE 9: Capacidad del Canal =====
        c_title = Text("Capacidad del Canal (C)", font_size=36, color=BLUE, font="Menlo")
        c_title.to_edge(UP, buff=0.5)

        c_desc = Text(
            "Máxima información transmisible de forma fiable",
            font_size=22, color=YELLOW, font="Menlo"
        )
        c_desc.next_to(c_title, DOWN, buff=0.5)

        # Key condition
        condition = MathTex(
            r"C \geq R",
            font_size=42, color=GREEN
        )
        condition.next_to(c_desc, DOWN, buff=0.5)

        cond_text = Text(
            "Condición para transmisión confiable",
            font_size=18, color=GREY_B, font="Menlo"
        )
        cond_text.next_to(condition, DOWN, buff=0.3)

        # If R > C
        bad_cond = MathTex(
            r"R > C \Rightarrow \text{errores inevitables}",
            font_size=26, color=RED
        )
        bad_cond.next_to(cond_text, DOWN, buff=0.5)

        self.play(Write(c_title), run_time=0.8)
        self.play(Write(c_desc), run_time=1)
        self.play(Write(condition), run_time=1)
        self.play(FadeIn(cond_text, shift=UP * 0.2), run_time=0.6)
        self.wait(0.5)
        self.play(Write(bad_cond), run_time=1)
        self.wait(1.5)
        self.play(FadeOut(Group(c_title, c_desc, condition, cond_text, bad_cond)))
        self.wait(0.3)

        # ===== SLIDE 10: Teorema de Shannon-Hartley =====
        sh_title = Text("Teorema de Shannon-Hartley", font_size=34, color=BLUE, font="Menlo")
        sh_title.to_edge(UP, buff=0.5)

        sh_formula = MathTex(
            r"C = \Delta f \cdot \log_2\!\left(1 + \frac{S}{N}\right)",
            font_size=42, color=YELLOW
        )
        sh_formula.shift(UP * 0.2)

        # Variables
        vars_group = VGroup(
            VGroup(
                MathTex(r"\Delta f", font_size=22, color=GREEN),
                Text("= ancho de banda [Hz]", font_size=16, color=GREY_B, font="Menlo"),
            ).arrange(RIGHT, buff=0.15),
            VGroup(
                MathTex(r"S", font_size=22, color=GREEN),
                Text("= potencia de señal [W]", font_size=16, color=GREY_B, font="Menlo"),
            ).arrange(RIGHT, buff=0.15),
            VGroup(
                MathTex(r"N", font_size=22, color=GREEN),
                Text("= potencia de ruido [W]", font_size=16, color=GREY_B, font="Menlo"),
            ).arrange(RIGHT, buff=0.15),
        ).arrange(DOWN, buff=0.3, aligned_edge=LEFT)
        vars_group.next_to(sh_formula, DOWN, buff=0.6)

        self.play(Write(sh_title), run_time=0.8)
        self.play(Write(sh_formula), run_time=1.8)
        self.play(LaggedStart(*[FadeIn(v, shift=RIGHT * 0.3) for v in vars_group], lag_ratio=0.25), run_time=1.5)
        self.wait(1.5)
        self.play(FadeOut(Group(sh_title, sh_formula, vars_group)))
        self.wait(0.3)

        # ===== SLIDE 11: Ejemplo canal telefónico =====
        ej_title = Text("Ejemplo: Canal Telefónico", font_size=32, color=BLUE, font="Menlo")
        ej_title.to_edge(UP, buff=0.5)

        data = VGroup(
            MathTex(r"\Delta f = 3000 \; \text{Hz}", font_size=26, color=GREEN),
            MathTex(r"S/N = 30 \; \text{dB} \approx 1000", font_size=26, color=GREEN),
        ).arrange(DOWN, buff=0.3, aligned_edge=LEFT).shift(UP * 0.8)

        step1 = MathTex(
            r"C = 3000 \cdot \log_2(1 + 1000)",
            font_size=26, color=WHITE
        )
        step1.next_to(data, DOWN, buff=0.6)

        step2 = MathTex(
            r"C = 3000 \cdot 9{,}97",
            font_size=26, color=WHITE
        )
        step2.next_to(step1, DOWN, buff=0.3)

        result = MathTex(
            r"C \approx 29.900 \; \text{bps}",
            font_size=30, color=YELLOW
        )
        result.next_to(step2, DOWN, buff=0.4)

        self.play(Write(ej_title), run_time=0.8)
        self.play(FadeIn(data, shift=DOWN * 0.2), run_time=1)
        self.play(Write(step1), run_time=1)
        self.play(Write(step2), run_time=0.8)
        self.play(Write(result), run_time=1)
        self.wait(2)
        self.play(FadeOut(Group(ej_title, data, step1, step2, result)))
        self.wait(0.3)

        # ===== SLIDE 12: Resumen =====
        res_title = Text("Resumen", font_size=36, color=BLUE, font="Menlo")
        res_title.to_edge(UP, buff=0.4)

        summary_items = VGroup(
            VGroup(
                MathTex(r"I(s) = \log_2(1/P(s))", font_size=24, color=WHITE),
                Text("Cantidad de información", font_size=16, color=GREY_B, font="Menlo"),
            ).arrange(RIGHT, buff=0.3, aligned_edge=ORIGIN),
            VGroup(
                MathTex(r"H = -\sum P(s_i)\log_2 P(s_i)", font_size=24, color=WHITE),
                Text("Entropía", font_size=16, color=GREY_B, font="Menlo"),
            ).arrange(RIGHT, buff=0.3, aligned_edge=ORIGIN),
            VGroup(
                MathTex(r"R = H / \tau", font_size=24, color=WHITE),
                Text("Tasa de información", font_size=16, color=GREY_B, font="Menlo"),
            ).arrange(RIGHT, buff=0.3, aligned_edge=ORIGIN),
            VGroup(
                MathTex(r"C = \Delta f \cdot \log_2(1+S/N)", font_size=24, color=WHITE),
                Text("Capacidad del canal", font_size=16, color=GREY_B, font="Menlo"),
            ).arrange(RIGHT, buff=0.3, aligned_edge=ORIGIN),
        ).arrange(DOWN, buff=0.4, aligned_edge=LEFT).shift(DOWN * 0.15)

        # Condition
        final_cond = MathTex(
            r"C \geq R \quad \text{→ transmisión confiable}",
            font_size=28, color=GREEN
        )
        final_cond.next_to(summary_items, DOWN, buff=0.6)

        self.play(Write(res_title), run_time=0.8)
        self.play(LaggedStart(*[FadeIn(s, shift=RIGHT * 0.4) for s in summary_items], lag_ratio=0.2), run_time=2)
        self.play(Write(final_cond), run_time=1.2)
        self.wait(2.5)

        # Fade out all
        self.play(FadeOut(Group(res_title, summary_items, final_cond)))
        self.wait(0.5)