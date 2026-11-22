package xtuml_java.generator.runtime;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Registri relasi (binary, associative, generalization), operasi relate/unrelate/navigate,
 * dan pengecekan kardinalitas.
 *
 * Batas atas dicek seketika saat relate(...). Batas bawah dicek lewat validate()
 * (dipanggil Runtime di akhir tiap action).
 *
 * Konvensi: multiplisitas di ujung A = jumlah instance A per satu instance B;
 *           multiplisitas di ujung B = jumlah instance B per satu instance A.
 */
public final class Relationships {
    private enum Kind { BINARY, ASSOCIATIVE, GENERALIZATION }

    private static final class Def {
        final String id;
        final Kind kind;
        Class<?> classA;
        Class<?> classB;
        Multiplicity multA;
        Multiplicity multB;
        String phraseA;
        String phraseB;
        Class<?> assocClass;
        // Class<?> superClass; // Belum digunakan dalam navigasi generalisasi.
        List<Class<?>> subClasses = new ArrayList<Class<?>>();

        Def(String id, Kind kind) {
            this.id = id;
            this.kind = kind;
        }
    }

    private static final class Link {
        final XtumlObject a;
        final XtumlObject b;
        final XtumlObject assoc;

        Link(XtumlObject a, XtumlObject b, XtumlObject assoc) {
            this.a = a;
            this.b = b;
            this.assoc = assoc;
        }
    }

    private static final Map<String, Def> DEFS = new LinkedHashMap<String, Def>();
    private static final Map<String, List<Link>> LINKS = new HashMap<String, List<Link>>();

    private Relationships() {
    }

    // ------------------------------------------------------------------ definisi

    public static void defineBinary(String id, Class<?> a, String multA, String phraseA,
                                    Class<?> b, String multB, String phraseB) {
        Def d = new Def(id, Kind.BINARY);
        fill(d, a, multA, phraseA, b, multB, phraseB);
        register(d);
    }

    public static void defineAssociative(String id, Class<?> a, String multA, String phraseA,
                                         Class<?> b, String multB, String phraseB, Class<?> assocClass) {
        Def d = new Def(id, Kind.ASSOCIATIVE);
        fill(d, a, multA, phraseA, b, multB, phraseB);
        d.assocClass = assocClass;
        register(d);
    }

    public static void defineGeneralization(String id, Class<?> superClass, Class<?>... subClasses) {
        Def d = new Def(id, Kind.GENERALIZATION);
        // d.superClass = superClass; // Relasi generalisasi saat ini hanya menyimpan subtype.
        for (Class<?> c : subClasses) {
            d.subClasses.add(c);
        }
        register(d);
    }

    private static void fill(Def d, Class<?> a, String multA, String phraseA,
                             Class<?> b, String multB, String phraseB) {
        d.classA = a;
        d.classB = b;
        d.multA = Multiplicity.parse(multA);
        d.multB = Multiplicity.parse(multB);
        d.phraseA = phraseA;
        d.phraseB = phraseB;
    }

    private static void register(Def d) {
        DEFS.put(d.id, d);
        LINKS.put(d.id, new ArrayList<Link>());
    }

    public static void reset() {
        DEFS.clear();
        LINKS.clear();
    }

    private static Def def(String id) {
        Def d = DEFS.get(id);
        if (d == null) {
            throw new IllegalArgumentException("Relasi tidak dikenal: " + id);
        }
        return d;
    }

    // ------------------------------------------------------------------ relate / unrelate

    public static void relate(String id, XtumlObject x, XtumlObject y) {
        relate(id, x, y, null);
    }

    /** relate x to y across id [using assoc]. Batas atas dicek seketika. */
    public static void relate(String id, XtumlObject x, XtumlObject y, XtumlObject assoc) {
        Def d = def(id);
        if (d.kind == Kind.GENERALIZATION) {
            throw new IllegalArgumentException(id + " adalah generalisasi; tidak perlu relate");
        }
        if (x == null || y == null) {
            throw new IllegalArgumentException("relate " + id + " dengan instance kosong");
        }
        XtumlObject a;
        XtumlObject b;
        if (d.classA.isInstance(x) && d.classB.isInstance(y)) {
            a = x;
            b = y;
        } else if (d.classA.isInstance(y) && d.classB.isInstance(x)) {
            a = y;
            b = x;
        } else {
            throw new IllegalArgumentException("relate " + id + ": tipe instance tidak cocok (" + x.describe()
                    + ", " + y.describe() + ")");
        }
        if (d.kind == Kind.ASSOCIATIVE) {
            if (assoc == null) {
                throw new IllegalArgumentException("relate " + id + " membutuhkan 'using' instance association class");
            }
            if (!d.assocClass.isInstance(assoc)) {
                throw new IllegalArgumentException("relate " + id + ": instance 'using' bukan "
                        + d.assocClass.getSimpleName());
            }
        }
        List<Link> list = LINKS.get(id);
        for (Link l : list) {
            if (l.a == a && l.b == b) {
                throw new IllegalStateException(a.describe() + " dan " + b.describe() + " sudah terhubung via " + id);
            }
        }
        int countA = countFor(list, a, true) + 1;
        if (!d.multB.withinUpper(countA)) {
            throw new CardinalityViolationException(id, a.describe() + " akan terhubung ke " + countA + " "
                    + d.classB.getSimpleName() + ", batas atas " + d.multB);
        }
        int countB = countFor(list, b, false) + 1;
        if (!d.multA.withinUpper(countB)) {
            throw new CardinalityViolationException(id, b.describe() + " akan terhubung ke " + countB + " "
                    + d.classA.getSimpleName() + ", batas atas " + d.multA);
        }
        list.add(new Link(a, b, assoc));
    }

    public static void unrelate(String id, XtumlObject x, XtumlObject y) {
        unrelate(id, x, y, null);
    }

    public static void unrelate(String id, XtumlObject x, XtumlObject y, XtumlObject assoc) {
        Def d = def(id);
        List<Link> list = LINKS.get(id);
        for (int i = 0; i < list.size(); i++) {
            Link l = list.get(i);
            if ((l.a == x && l.b == y) || (l.a == y && l.b == x)) {
                list.remove(i);
                return;
            }
        }
        throw new IllegalStateException("unrelate " + d.id + ": " + x + " dan " + y + " tidak terhubung");
    }

    /** Dipanggil Store.delete: melepas semua link yang melibatkan obj. */
    static void removeAll(XtumlObject obj) {
        for (List<Link> list : LINKS.values()) {
            for (int i = list.size() - 1; i >= 0; i--) {
                Link l = list.get(i);
                if (l.a == obj || l.b == obj || l.assoc == obj) {
                    list.remove(i);
                }
            }
        }
    }

    private static int countFor(List<Link> list, XtumlObject obj, boolean asA) {
        int n = 0;
        for (Link l : list) {
            if ((asA ? l.a : l.b) == obj) {
                n++;
            }
        }
        return n;
    }

    // ------------------------------------------------------------------ navigasi

    public static <T> List<T> navigate(XtumlObject from, String id, Class<T> target, String phrase) {
        List<T> out = new ArrayList<T>();
        if (from == null) {
            return out;
        }
        Def d = def(id);
        if (d.kind == Kind.GENERALIZATION) {
            if (target.isInstance(from)) {
                out.add(target.cast(from));
            }
            return out;
        }
        boolean aOk = phrase == null || phrase.equals(d.phraseA);
        boolean bOk = phrase == null || phrase.equals(d.phraseB);
        for (Link l : LINKS.get(id)) {
            XtumlObject found = null;
            if (l.assoc != null && l.assoc == from) {
                found = target.isInstance(l.a) ? l.a : (target.isInstance(l.b) ? l.b : null);
            } else if (l.a == from && aOk) {
                found = pick(l, l.b, target);
            } else if (l.b == from && bOk) {
                found = pick(l, l.a, target);
            }
            if (found != null && !out.contains(target.cast(found))) {
                out.add(target.cast(found));
            }
        }
        return out;
    }

    private static XtumlObject pick(Link l, XtumlObject partner, Class<?> target) {
        if (l.assoc != null && target.isInstance(l.assoc)) {
            return l.assoc;
        }
        return target.isInstance(partner) ? partner : null;
    }

    /** Navigasi dari banyak instance sekaligus (rantai ->A[R1]->B[R2]). Hasil tanpa duplikat. */
    public static <T> List<T> navigateAll(Collection<? extends XtumlObject> from, String id,
                                          Class<T> target, String phrase) {
        List<T> out = new ArrayList<T>();
        if (from == null) {
            return out;
        }
        for (XtumlObject f : from) {
            for (T t : navigate(f, id, target, phrase)) {
                if (!out.contains(t)) {
                    out.add(t);
                }
            }
        }
        return out;
    }

    public static <T> T navigateOne(XtumlObject from, String id, Class<T> target, String phrase) {
        return Ops.first(navigate(from, id, target, phrase));
    }

    public static boolean isRelated(String id, XtumlObject x, XtumlObject y) {
        for (Link l : LINKS.get(id)) {
            if ((l.a == x && l.b == y) || (l.a == y && l.b == x)) {
                return true;
            }
        }
        return false;
    }

    // ------------------------------------------------------------------ validasi batas bawah

    /** Memeriksa batas bawah semua relasi untuk semua instance hidup. */
    public static void validate() {
        StringBuilder problems = new StringBuilder();
        String firstId = null;
        for (Def d : DEFS.values()) {
            if (d.kind == Kind.GENERALIZATION) {
                continue;
            }
            List<Link> list = LINKS.get(d.id);
            for (XtumlObject o : Store.liveInstances()) {
                if (d.classA.isInstance(o)) {
                    int n = countFor(list, o, true);
                    if (!d.multB.satisfiedBy(n)) {
                        firstId = firstId == null ? d.id : firstId;
                        append(problems, d.id, o, n, d.classB, d.multB);
                    }
                }
                if (d.classB.isInstance(o)) {
                    int n = countFor(list, o, false);
                    if (!d.multA.satisfiedBy(n)) {
                        firstId = firstId == null ? d.id : firstId;
                        append(problems, d.id, o, n, d.classA, d.multA);
                    }
                }
            }
        }
        if (problems.length() > 0) {
            throw new CardinalityViolationException(firstId, problems.toString().trim());
        }
    }

    private static void append(StringBuilder sb, String id, XtumlObject o, int n, Class<?> other, Multiplicity m) {
        sb.append(id).append(": ").append(o.describe()).append(" terhubung ke ").append(n).append(' ')
                .append(other.getSimpleName()).append(", seharusnya ").append(m).append("; ");
    }
}
