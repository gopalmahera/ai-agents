"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.mongoConfigured = mongoConfigured;
exports.getDb = getDb;
exports.mongoHealth = mongoHealth;
const mongodb_1 = require("mongodb");
const MONGO_URL = process.env.MONGO_URL || "";
const MONGO_DB = process.env.MONGO_DB || "alert_agent";
let client = null;
let db = null;
let indexesReady = false;
function mongoConfigured() {
    return Boolean(MONGO_URL);
}
async function getDb() {
    if (!MONGO_URL) {
        throw new Error("MONGO_URL is not configured");
    }
    if (db)
        return db;
    client = new mongodb_1.MongoClient(MONGO_URL, { serverSelectionTimeoutMS: 5000 });
    await client.connect();
    db = client.db(MONGO_DB);
    if (!indexesReady) {
        await ensureIndexes(db);
        indexesReady = true;
    }
    return db;
}
async function ensureIndexes(database) {
    await database.collection("endpoints").createIndex({ name: 1 }, { unique: true });
    await database.collection("environments").createIndex({ name: 1 }, { unique: true });
    await database.collection("routing_rules").createIndex({ id: 1 }, { unique: true });
    await database.collection("routing_rules").createIndex({ order: 1 });
    await database.collection("time_intervals").createIndex({ name: 1 }, { unique: true });
    await database.collection("time_intervals").createIndex({ order: 1 });
    await database.collection("silences").createIndex({ id: 1 }, { unique: true });
    await database.collection("silences").createIndex({ status: 1 });
    await database.collection("alert_events").createIndex({ ts: -1 });
}
async function mongoHealth() {
    if (!MONGO_URL)
        return false;
    try {
        const database = await getDb();
        await database.command({ ping: 1 });
        return true;
    }
    catch {
        return false;
    }
}
//# sourceMappingURL=mongo.js.map