"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.computeHash = computeHash;
const crypto_1 = require("crypto");
function computeHash(payload) {
    const canonical = JSON.stringify(payload, Object.keys(payload).sort());
    return (0, crypto_1.createHash)('sha256').update(canonical).digest('hex');
}
//# sourceMappingURL=hash.js.map