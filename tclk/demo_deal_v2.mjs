#!/usr/bin/env node
// Technochad tclk deal v2 — correct contract-id propagation + stranger fold.
// Flow: offer(payer) -> accept(payee) -> rail record FIRST -> lock(payer)
//       -> rail 'claimed' -> reveal(payee) -> receipt(payer) -> verify as a stranger.
import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { writeFileSync } from "node:fs";

import {
  OFFER_ROOM, encodeFrame, makeOffer, makeAccept, generateHashLock,
  encodePaperRecord, paperNote, validateFrame, verifyHashPreimage,
  applyFrame, openContract, decodeFrame,
} from "@flop-labs/tclk";

const STARTER = "/home/user/technocore-did-starter";
const VENUE = "https://technocore.chat";
const DIDS = {
  planner: "did:key:z6Mkem9tMaHQwhz6ewwZReHv8ccj9RwikKu5hDSDRus6wLBB",
  implementer: "did:key:z6MkpEG6QUeApzQ5cyEsAv9h8PxVndn3ef56BJVBDg5j1Lr9",
};
const log = (s, d) => console.log(`${String(s).padEnd(3)} ${d}`);
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

function say(role, room, text) {
  const pass = execFileSync("cat", [`${STARTER}/identities/${role}.pass`]).toString().trim() + "\n";
  const out = execFileSync(`${STARTER}/.venv/bin/python`,
    ["technocore_agent.py", "say", "--key", `identities/${role}.pem`, room, text],
    { cwd: STARTER, input: pass, timeout: 120000 }).toString();
  const posted = JSON.parse(out.trim()).posted;
  console.log(`    seq ${posted.seq} <${role}>`);
  return posted;
}

function kvPost(ns, key, value, condition) {
  const body = JSON.stringify(condition ? { value, ...condition } : { value });
  const out = execFileSync("curl", ["-s", "--max-time", "25", "-X", "POST",
    "-H", "Content-Type: application/json", "-d", body, `${VENUE}/kv/${ns}/${key}`],
    { maxBuffer: 8 * 1024 * 1024 }).toString();
  if (!out.startsWith("ok")) throw new Error(`KV set failed: ${out.slice(0, 120)}`);
}

function kvGet(ns, key) {
  return execFileSync("curl", ["-s", "--max-time", "25", `${VENUE}/kv/${ns}/${key}`],
    { maxBuffer: 8 * 1024 * 1024 }).toString();
}

const now = Date.now();
log("1", "OFFER (planner = payer)");
const offer = makeOffer({
  from: DIDS.planner, role: "payer", amount: "100", asset: "PAPER",
  lock: "hash", rails: ["paper"],
  claimByMs: now + 30 * 60_000, refundAfterMs: now + 60 * 60_000, expiresMs: now + 20 * 60_000,
  nonce: randomBytes(8).toString("hex"),
});
say("planner", OFFER_ROOM, encodeFrame(offer));
await sleep(2500);

log("2", "ACCEPT (implementer = payee)");
const { preimage, hash: statement } = generateHashLock();
const accept = makeAccept(offer, { from: DIDS.implementer, statement,
  nonce: randomBytes(8).toString("hex") });
const contract = accept.contract;              // ← the single source of truth
console.log(`    contract: ${contract}`);
say("implementer", OFFER_ROOM, encodeFrame(accept));
await sleep(2500);

log("3", "RAIL RECORD FIRST, then LOCK");
const note = paperNote(contract);
const locked = encodePaperRecord({ status: "locked", lock: "hash", statement,
  refundAfterMs: offer.refundAfterMs });
kvPost(note.ns, note.key, locked, { ifAbsent: true });
console.log(`    rail: ${note.ns}/${note.key} = locked`);
const lock = { type: "lock", from: DIDS.planner, contract, rail: "paper", ref: contract };
validateFrame(lock);
say("planner", OFFER_ROOM, encodeFrame(lock));
await sleep(2500);

log("4", "REVEAL (payee claims)");
if (!verifyHashPreimage(statement, preimage)) throw new Error("preimage mismatch");
kvPost(note.ns, note.key, encodePaperRecord({ status: "claimed", lock: "hash", statement,
  refundAfterMs: offer.refundAfterMs, secret: preimage }), { if: locked });
const reveal = { type: "reveal", from: DIDS.implementer, contract, secret: preimage };
validateFrame(reveal);
say("implementer", OFFER_ROOM, encodeFrame(reveal));
await sleep(2500);

log("5", "RECEIPT (payer closes)");
const receipt = { type: "receipt", from: DIDS.planner, contract, outcome: "claimed",
  rail: "paper", ref: contract };
validateFrame(receipt);
say("planner", OFFER_ROOM, encodeFrame(receipt));

log("6", "STRANGER FOLD — re-read the board and verify independently");
await sleep(3000);
const raw = execFileSync("curl", ["-s", "--max-time", "30", `${VENUE}/r/${OFFER_ROOM}/export`],
  { maxBuffer: 64 * 1024 * 1024 }).toString();
const frames = [];
for (const line of raw.split("\n")) {
  if (!line.trim().startsWith("{")) continue;
  try {
    const rec = JSON.parse(line);
    if ((rec.text || "").startsWith("tclk1 ")) {
      const f = decodeFrame(rec.text);
      if (f.type === "offer" ? f.id === offer.id : f.contract === contract) frames.push(f);
    }
  } catch { /* skip */ }
}
console.log(`    board frames for this contract: ${frames.length} (expect 5)`);
let state = openContract(offer);
for (const f of frames) {
  const step = applyFrame(state, f, Date.now());
  state = step.state ?? step;
}
console.log(`    folded status: ${state.status}  (expect: claimed)`);
const railNow = kvGet(note.ns, note.key).split("\n").filter(l => l.includes("tclkpaper")).pop() || "";
console.log(`    rail now: ${railNow.slice(0, 80)}`);
const okRail = railNow.startsWith("tclkpaper1 claimed");
console.log(`    rail consistent: ${okRail}`);

writeFileSync("/home/user/tclk-work/deal-v2.json", JSON.stringify({
  offer, accept, contract, lock, reveal, receipt, note, preimage, statement,
  foldedStatus: state.status, railOk: okRail }, null, 2));
log("7", okRail && state.status === "claimed"
  ? "DEAL VERIFIED END-TO-END — artifacts in deal-v2.json"
  : "MISMATCH — inspect deal-v2.json");
