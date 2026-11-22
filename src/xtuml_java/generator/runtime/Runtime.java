package xtuml_java.generator.runtime;
import java.util.ArrayDeque;
import java.util.Deque;

/**
 * Mesin event: antrean event dengan prioritas untuk event-ke-diri-sendiri.
 * Setelah setiap action (dispatch) selesai, batas bawah multiplisitas dicek lewat Relationships.validate().
 */
public final class Runtime {
    private static final int MAX_EVENTS = 100000;

    private static final class Pending {
        final XtumlObject target;
        final Event event;

        Pending(XtumlObject target, Event event) {
            this.target = target;
            this.event = event;
        }
    }

    private static final Deque<Pending> SELF_QUEUE = new ArrayDeque<Pending>();
    private static final Deque<Pending> NORMAL_QUEUE = new ArrayDeque<Pending>();
    private static XtumlObject current = null;
    private static int processed = 0;

    private Runtime() {
    }

    /** generate Event to target; event ke diri sendiri diproses lebih dulu daripada event lain. */
    public static void generate(XtumlObject target, Event event) {
        if (target == null) {
            Ops.logFailure("generate " + event.getName() + " ke instance kosong diabaikan");
            return;
        }
        if (target.isDeleted()) {
            Ops.logFailure("generate " + event.getName() + " ke instance terhapus (" + target.describe() + ") diabaikan");
            return;
        }
        Pending p = new Pending(target, event);
        if (current != null && current == target) {
            SELF_QUEUE.addLast(p);
        } else {
            NORMAL_QUEUE.addLast(p);
        }
    }

    public static boolean hasPending() {
        return !SELF_QUEUE.isEmpty() || !NORMAL_QUEUE.isEmpty();
    }

    public static int pendingCount() {
        return SELF_QUEUE.size() + NORMAL_QUEUE.size();
    }

    /** Memproses semua event sampai antrean kosong. */
    public static void run() {
        Relationships.validate();
        while (hasPending()) {
            Pending p = SELF_QUEUE.isEmpty() ? NORMAL_QUEUE.pollFirst() : SELF_QUEUE.pollFirst();
            if (p.target.isDeleted()) {
                Ops.logFailure("event " + p.event.getName() + " untuk instance terhapus diabaikan");
                continue;
            }
            if (++processed > MAX_EVENTS) {
                throw new IllegalStateException("Batas jumlah event terlampaui (kemungkinan loop tak hingga)");
            }
            current = p.target;
            try {
                p.target.dispatch(p.event);
            } finally {
                current = null;
            }
            Relationships.validate();
        }
    }

    public static void reset() {
        SELF_QUEUE.clear();
        NORMAL_QUEUE.clear();
        current = null;
        processed = 0;
    }
}