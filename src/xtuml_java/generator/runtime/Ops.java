package xtuml_java.generator.runtime;

import java.util.Collection;
import java.util.List;
import java.util.Objects;

/** Fungsi bantu statis yang dipakai kode hasil terjemahan OAL (log, empty/cardinality, dll). */
public final class Ops {
    private Ops() {
    }

    public static void logInfo(Object message) {
        System.out.println("[INFO]  " + message);
    }

    public static void logFailure(Object message) {
        System.out.println("[FAIL]  " + message);
    }

    public static void logState(Object message) {
        System.out.println("[STATE] " + message);
    }

    public static boolean empty(Collection<?> c) {
        return c == null || c.isEmpty();
    }

    public static boolean empty(Object o) {
        return o == null;
    }

    public static boolean notEmpty(Collection<?> c) {
        return !empty(c);
    }

    public static boolean notEmpty(Object o) {
        return o != null;
    }

    public static int cardinality(Collection<?> c) {
        return c == null ? 0 : c.size();
    }

    public static int cardinality(Object o) {
        return o == null ? 0 : 1;
    }

    /** Kesetaraan nilai (aman untuk null, dipakai untuk string). */
    public static boolean eq(Object a, Object b) {
        return Objects.equals(a, b);
    }

    /** Membungkus konstanta boolean agar javac tidak menganggap kode sesudahnya unreachable. */
    public static boolean bool(boolean b) {
        return b;
    }

    public static <T> T first(List<T> list) {
        return (list == null || list.isEmpty()) ? null : list.get(0);
    }
}