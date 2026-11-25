"""Generator class Java: atribut, getter/setter, operasi (OAL), dan state machine."""
from __future__ import annotations

from typing import List, Optional

from ..ir.model import Model, Operation, XtClass, cap, getter_name, safe_ident, setter_name
from ..oal.translator import translate_action
from . import generalization_gen, relation_gen
from .state_machine_gen import generate_state_machine


def _signature(model: Model, op: Operation) -> str:
    params = ", ".join(f"{model.java_type(p.type)} {safe_ident(p.name)}" for p in op.params)
    return f"{model.java_type(op.return_type)} {op.name}({params})"


def _operation(model: Model, cls: XtClass, op: Operation, todos: Optional[List[str]]) -> List[str]:
    if op.is_abstract:
        return [f"    public abstract {_signature(model, op)};", ""]
    overriding = any(model.find_operation(a, op.name) for a in model.ancestors(cls))
    res = translate_action(model, op.body, cls=cls, params={p.name: p.type for p in op.params},
                           return_type=op.return_type, kind="operation", indent=2)
    if todos is not None:
        todos.extend(f"{cls.name}.{op.name}: {t}" for t in res.todos)
    head = ["    @Override"] if overriding else []
    return head + [f"    public {_signature(model, op)} {{", *res.lines, "    }", ""]


def generate_class(model: Model, cls: XtClass, todos: Optional[List[str]] = None) -> str:
    L: List[str] = [f"package {model.package};", ""]
    doc = [f"Class xtUML: {cls.name} ({cls.key_letters})"] + relation_gen.relationship_comments(model, cls)
    L.append("/**")
    L += [f" * {d}" for d in doc]
    L.append(" */")
    L.append(generalization_gen.class_declaration(model, cls) + " {")
    L.append("")
    for a in cls.attributes:
        L.append(f"    private {model.java_type(a.type)} {safe_ident(a.name)} = {model.java_default(a.type)};")
    if cls.attributes:
        L.append("")
    L += [f"    public {cls.name}() {{", "        super();", "    }", "",
          "    @Override", "    public String getKeyLetters() {", f'        return "{cls.key_letters}";', "    }", ""]
    for a in cls.attributes:
        jt, n = model.java_type(a.type), safe_ident(a.name)
        L += [f"    public {jt} {getter_name(a.name)}() {{", f"        return this.{n};", "    }", "",
              f"    public void {setter_name(a.name)}({jt} value) {{", f"        this.{n} = value;", "    }", ""]
    for op in cls.operations:
        L += _operation(model, cls, op, todos)
    if cls.state_machine is not None:
        L += generate_state_machine(model, cls, todos)
    while L and L[-1] == "":
        L.pop()
    L.append("}")
    imports: List[str] = []
    if any("List<" in line for line in L):
        imports.append("import java.util.List;")
    if any("ArrayList<" in line for line in L):
        imports.append("import java.util.ArrayList;")
    if imports:
        L[2:2] = imports + [""]
    return "\n".join(L) + "\n"