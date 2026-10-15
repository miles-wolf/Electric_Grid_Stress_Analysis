import fitz

d = fitz.open(r"C:\Users\mltsw\OneDrive\Desktop\Projects\grid-fragility-analysis\Electric Grid Fragility Analysis.pdf")
out = []
for i, p in enumerate(d):
    out.append(f"===== PAGE {i+1} =====")
    out.append(p.get_text())
    # note images on each page
    imgs = p.get_images(full=True)
    out.append(f"[{len(imgs)} images on page]")

with open(r"C:\Users\mltsw\OneDrive\Desktop\Projects\grid-fragility-analysis\_report_build\prev_report_text.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("done")
