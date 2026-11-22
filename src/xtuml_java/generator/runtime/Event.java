package xtuml_java.generator.runtime;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/** Event xtUML: nama + parameter opsional. Event dikirim ke instance lewat Runtime.generate(...). */
public final class Event {
    private final String name;
    private final Map<String, Object> params;

    public Event(String name) {
        this(name, Collections.<String, Object>emptyMap());
    }

    public Event(String name, Map<String, Object> params) {
        this.name = name;
        this.params = Collections.unmodifiableMap(new LinkedHashMap<String, Object>(params));
    }

    /** Pembuat ringkas: Event.of("Nama", "p1", nilai1, "p2", nilai2). */
    public static Event of(String name, Object... keyValues) {
        if (keyValues.length % 2 != 0) {
            throw new IllegalArgumentException("Event.of membutuhkan pasangan nama/nilai parameter");
        }
        Map<String, Object> map = new LinkedHashMap<String, Object>();
        for (int i = 0; i < keyValues.length; i += 2) {
            map.put(String.valueOf(keyValues[i]), keyValues[i + 1]);
        }
        return new Event(name, map);
    }

    public String getName() {
        return name;
    }

    public Map<String, Object> getParams() {
        return params;
    }

    public Object get(String paramName) {
        return params.get(paramName);
    }

    @Override
    public String toString() {
        return params.isEmpty() ? name : name + params;
    }
}