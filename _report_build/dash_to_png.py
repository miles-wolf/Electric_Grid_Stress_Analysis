import fitz

base = r"C:\Users\mltsw\OneDrive\Desktop\Projects\grid-fragility-analysis"
for n in (1, 2, 3):
    src = rf"{base}\reports\dashboard\Grid-Stress-Analysis_Dashboard_{n}.pdf"
    d = fitz.open(src)
    print(src, "pages:", d.page_count)
    for i, p in enumerate(d):
        pix = p.get_pixmap(dpi=170)
        out = rf"{base}\_report_build\dashboard_{n}_p{i+1}.png"
        pix.save(out)
        print("  saved", out, pix.width, "x", pix.height)
