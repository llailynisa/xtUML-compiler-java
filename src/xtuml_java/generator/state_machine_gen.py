"""Generator State Machine Java untuk XtClass yang memiliki StateMachine."""
from __future__ import annotations

from typing import Dict, List, Optional

from ..ir.model import EventDef, Model, Transition, TypeRef, XtClass, const_name
from ..oal.translator import translate_action


def _event_params_for_state(sm_events: List[EventDef], transitions: List[Transition], state_name: str) -> Dict[str, TypeRef]:
    """Mengumpulkan tipe parameter dari event-event yang masuk ke state_name agar rcvd_evt aman."""
    incoming_events = {t.event for t in transitions if t.target == state_name}
    ev_map = {e.name: e for e in sm_events}
    params: Dict[str, TypeRef] = {}
    for ev_name in incoming_events:
        ev_def = ev_map.get(ev_name)
        if ev_def:
            for p in ev_def.params:
                params[p.name] = p.type
    return params


def generate_state_machine(model: Model, cls: XtClass, todos: Optional[List[str]] = None) -> List[str]:
    """Menghasilkan blok kode Java (List[str]) untuk State Machine di dalam tubuh class."""
    sm = cls.state_machine
    if sm is None:
        return []

    lines: List[str] = []

    # 1. Enum State dengan label nama asli state
    lines.append("    public enum State {")
    for idx, st in enumerate(sm.states):
        sep = "," if idx < len(sm.states) - 1 else ";"
        lines.append(f'        {const_name(st.name)}("{st.name}"){sep}')
    lines.append("")
    lines.append("        private final String label;")
    lines.append("        State(String label) { this.label = label; }")
    lines.append("        @Override public String toString() { return label; }")
    lines.append("    }")
    lines.append("")

    # 2. Field currentState & getter getCurrentState()
    init_const = const_name(sm.initial)
    lines.append(f"    protected State currentState = State.{init_const};")
    lines.append("")
    lines.append("    public State getCurrentState() {")
    lines.append("        return this.currentState;")
    lines.append("    }")
    lines.append("")

    # 3. dispatch(Event event)
    lines.append("    @Override")
    lines.append("    public void dispatch(Event event) {")
    lines.append("        if (event == null) {")
    lines.append("            return;")
    lines.append("        }")
    lines.append("        switch (this.currentState) {")

    for st in sm.states:
        st_const = const_name(st.name)
        outgoing = [t for t in sm.transitions if t.source == st.name]
        lines.append(f"            case {st_const}:")
        if outgoing:
            for idx, tr in enumerate(outgoing):
                kw = "if" if idx == 0 else "} else if"
                dst_const = const_name(tr.target)
                lines.append(f'                {kw} (event.getName().equals("{tr.event}")) {{')
                lines.append(f"                    enter(State.{dst_const}, event);")
            lines.append("                } else {")
            lines.append('                    Ops.logFailure(describe() + " mengabaikan event " + event.getName() + " pada state " + this.currentState);')
            lines.append("                }")
        else:
            lines.append('                Ops.logFailure(describe() + " mengabaikan event " + event.getName() + " pada state " + this.currentState);')
        lines.append("                break;")

    lines.append("        }")
    lines.append("    }")
    lines.append("")

    # 4. enter(State next, Event rcvd_evt)
    lines.append("    private void enter(State next, Event rcvd_evt) {")
    lines.append("        this.currentState = next;")
    lines.append('        Ops.logState(describe() + " -> " + next);')
    lines.append("        switch (next) {")
    for st in sm.states:
        st_const = const_name(st.name)
        lines.append(f"            case {st_const}:")
        lines.append(f"                action_{st.name}(rcvd_evt);")
        lines.append("                break;")
    lines.append("        }")
    lines.append("    }")
    lines.append("")

    # 5. action_<State>(Event rcvd_evt)
    for st in sm.states:
        ev_params = _event_params_for_state(sm.events, sm.transitions, st.name)
        res = translate_action(
            model,
            st.action,
            cls=cls,
            params=ev_params,
            kind="state",
            indent=2,
        )
        if todos is not None:
            todos.extend(f"{cls.name}.{st.name}: {t}" for t in res.todos)

        lines.append(f"    private void action_{st.name}(Event rcvd_evt) {{")
        if res.lines:
            lines.extend(res.lines)
        lines.append("    }")
        lines.append("")

    return lines