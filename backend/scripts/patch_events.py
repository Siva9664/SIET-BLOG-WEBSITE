import re, sys, pathlib
p = pathlib.Path(sys.argv[1])
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
sc = [i for i, l in enumerate(lines) if l.strip() == "structured_content = {"]
assert len(sc) == 1, f"expected 1 'structured_content = {{', found {len(sc)}"
s0 = sc[0]
start = next(i for i in range(s0, len(lines)) if lines[i].strip() == '"achievements": [')
end = next(i for i in range(start, len(lines)) if lines[i].strip() == '"captions": [')
assert "Excellence in Applied Research" in "".join(lines[start:end]), "anchored on the wrong block"
indent = re.match(r"[ \t]*", lines[start]).group(0)
new = f'''{indent}"achievements": [],  # never invent awards; leave empty when the source has none
{indent}"events": (
{indent}    [
{indent}        {{
{indent}            "title": active_event_name,
{indent}            "description": (paragraphs[1][:240] if len(paragraphs) > 1 else ""),
{indent}            "date": active_event_date,
{indent}        }}
{indent}    ]
{indent}    if active_event_name and active_event_date
{indent}    else []
{indent}),
''' 
lines[start:end] = [new]
p.write_text("".join(lines), encoding="utf-8")
print(f"replaced lines {start+1}-{end} ({len(indent)} spaces)")
