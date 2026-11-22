package xtuml_java.generator.runtime;
/**
 * Kelas dasar semua instance hasil generate. Setiap instance otomatis terdaftar di Store.
 * Kelas bersistem state machine meng-override dispatch(Event).
 */
public abstract class XtumlObject {
    private static long counter = 0;

    private final long instanceId;
    private boolean deleted = false;

    protected XtumlObject() {
        this.instanceId = ++counter;
        Store.register(this);
    }

    public long getInstanceId() {
        return instanceId;
    }

    /** Key letters kelas (mis. "SLOT"). */
    public abstract String getKeyLetters();

    public boolean isDeleted() {
        return deleted;
    }

    void markDeleted() {
        this.deleted = true;
    }

    /** Dipanggil Runtime saat event untuk instance ini diproses. Default: tidak ada state machine. */
    public void dispatch(Event event) {
        Ops.logInfo(describe() + " tidak memiliki state machine; event " + event.getName() + " diabaikan");
    }

    public String describe() {
        return getClass().getSimpleName() + "#" + instanceId;
    }

    @Override
    public String toString() {
        return describe();
    }
}