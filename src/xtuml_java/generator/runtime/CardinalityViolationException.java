package xtuml_java.generator.runtime;

/** Dilempar saat batas atas (saat relate) atau batas bawah (saat validate) suatu relasi dilanggar. */
public class CardinalityViolationException extends RuntimeException {
    private static final long serialVersionUID = 1L;

    private final String relationshipId;

    public CardinalityViolationException(String relationshipId, String message) {
        super("[" + relationshipId + "] " + message);
        this.relationshipId = relationshipId;
    }

    public String getRelationshipId() {
        return relationshipId;
    }
}