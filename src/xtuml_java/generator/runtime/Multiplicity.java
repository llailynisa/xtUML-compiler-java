package xtuml_java.generator.runtime;

/**
 * Batas jumlah relasi (kardinalitas) pada satu ujung relasi, mis. "1", "0..*", "1..*", "0..2".
 * Konvensi UML: multiplisitas di ujung X = jumlah instance X yang terhubung ke SATU instance di ujung lawan.
 */
public final class Multiplicity {
    public static final int UNBOUNDED = Integer.MAX_VALUE;

    private final int lower;
    private final int upper;

    public Multiplicity(int lower, int upper) {
        if (lower < 0 || upper < lower) {
            throw new IllegalArgumentException("Multiplisitas tidak valid: " + lower + ".." + upper);
        }
        this.lower = lower;
        this.upper = upper;
    }

    /** Mem-parse teks seperti "1", "*", "0..*", "1..*", "2..5". */
    public static Multiplicity parse(String text) {
        String t = text.trim();
        if (t.equals("*")) {
            return new Multiplicity(0, UNBOUNDED);
        }
        int idx = t.indexOf("..");
        if (idx < 0) {
            int n = Integer.parseInt(t);
            return new Multiplicity(n, n);
        }
        int lo = Integer.parseInt(t.substring(0, idx).trim());
        String hiText = t.substring(idx + 2).trim();
        int hi = hiText.equals("*") ? UNBOUNDED : Integer.parseInt(hiText);
        return new Multiplicity(lo, hi);
    }

    public int getLower() {
        return lower;
    }

    public int getUpper() {
        return upper;
    }

    public boolean isUnbounded() {
        return upper == UNBOUNDED;
    }

    /** Apakah jumlah ini masih berada di bawah/pada batas atas? */
    public boolean withinUpper(int count) {
        return count <= upper;
    }

    /** Apakah jumlah ini memenuhi batas bawah? */
    public boolean withinLower(int count) {
        return count >= lower;
    }

    public boolean satisfiedBy(int count) {
        return withinLower(count) && withinUpper(count);
    }

    @Override
    public String toString() {
        if (lower == upper) {
            return Integer.toString(lower);
        }
        return lower + ".." + (isUnbounded() ? "*" : Integer.toString(upper));
    }
}
