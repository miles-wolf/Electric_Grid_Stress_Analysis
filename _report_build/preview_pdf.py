import sys
import fitz

pdf = r"C:\Users\mltsw\OneDrive\Desktop\Projects\grid-fragility-analysis\Grid_Stress_Analysis_Report.pdf"
d = fitz.open(pdf)
print("pages:", d.page_count)
pages = [int(a) for a in sys.argv[1:]] if len(sys.argv) > 1 else range(1, d.page_count + 1)
for n in pages:
    p = d[n - 1]
    pix = p.get_pixmap(dpi=70)
    out = rf"C:\Users\mltsw\OneDrive\Desktop\Projects\grid-fragility-analysis\_report_build\preview_p{n:02d}.png"
    pix.save(out)
    print("saved", out)
