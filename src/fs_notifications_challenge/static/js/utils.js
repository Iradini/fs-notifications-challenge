
// Parts of a validation error's `loc`that mean nothing to a user: where the
// value came from ("body") and which channel schema validate it ("EMAIL")
const NOISE_IN_LOC = new Set(["body", "EMAIL", "SMS", "PUSH"]);

// Error message extraction from API responses
export function getErrorMessage(error) {
    if (typeof error.detail === "string") {
        return error.detail;  // domain errors (404/409/422) come as sentence
    } else if (Array.isArray(error.detail)) {
        // Validation errors: one per field. Say whic field, or two different
        // errors read as the same sentence twice
        const messages = error.detail.map((err) => {
            const field = (err.loc || []).filter((part) => !NOISE_IN_LOC.has(part)).join(".");
            const msg = err.msg.replace(/^Value error, /, "");
            return field ? `${field}: ${msg}` : msg; 
        });
        return [...new Set(messages)].join(". ");
    }
    return "An error occurred. Please try again.";
}

// Show a Bootstrap modal by ID
export function showModal(modalId) {
    const modal = bootstrap.Modal.getOrCreateInstance(
        document.getElementById(modalId),
    );
    modal.show();
    return modal;
}

// Hide a Bootstrap modal by ID
export function hideModal(modalId){
    const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById(modalId));
    if (modal) modal.hide();
}