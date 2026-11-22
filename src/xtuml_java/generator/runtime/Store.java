package xtuml_java.generator.runtime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.function.Predicate;

/** Penyimpanan semua instance hidup. Select pada supertype ikut mengembalikan instance subtype. */
public final class Store {
    private static final List<XtumlObject> INSTANCES = new ArrayList<XtumlObject>();

    private Store() {
    }

    static void register(XtumlObject obj) {
        INSTANCES.add(obj);
    }

    /** Menghapus instance beserta seluruh link relasinya. */
    public static void delete(XtumlObject obj) {
        if (obj == null || obj.isDeleted()) {
            return;
        }
        Relationships.removeAll(obj);
        obj.markDeleted();
        INSTANCES.remove(obj);
    }

    /** Semua instance hidup bertipe cls (termasuk subtype). */
    public static <T> List<T> all(Class<T> cls) {
        List<T> result = new ArrayList<T>();
        for (XtumlObject o : INSTANCES) {
            if (cls.isInstance(o)) {
                result.add(cls.cast(o));
            }
        }
        return result;
    }

    public static <T> List<T> selectMany(Class<T> cls, Predicate<T> where) {
        List<T> result = new ArrayList<T>();
        for (T t : all(cls)) {
            if (where == null || where.test(t)) {
                result.add(t);
            }
        }
        return result;
    }

    public static <T> T selectAny(Class<T> cls, Predicate<T> where) {
        for (T t : all(cls)) {
            if (where == null || where.test(t)) {
                return t;
            }
        }
        return null;
    }

    public static int count(Class<?> cls) {
        return all(cls).size();
    }

    public static List<XtumlObject> liveInstances() {
        return Collections.unmodifiableList(new ArrayList<XtumlObject>(INSTANCES));
    }

    public static void reset() {
        INSTANCES.clear();
    }
}