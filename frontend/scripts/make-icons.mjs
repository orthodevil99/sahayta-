/**
 * scripts/make-icons.mjs — dependency-free PNG icon generator.
 * Draws a white alert-triangle + exclamation on Sahayta brand blue.
 * Run: node scripts/make-icons.mjs
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";

const here = dirname(fileURLToPath(import.meta.url));
const outDir = join(here, "..", "public", "icons");
mkdirSync(outDir, { recursive: true });

const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c;
  }
  return t;
})();
function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const td = Buffer.from(type);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(Buffer.concat([td, data])));
  return Buffer.concat([len, td, data, crc]);
}
function png(w, h, rgba) {
  const raw = Buffer.alloc((w * 4 + 1) * h);
  for (let y = 0; y < h; y++) {
    raw[y * (w * 4 + 1)] = 0;
    rgba.copy(raw, y * (w * 4 + 1) + 1, y * w * 4, (y + 1) * w * 4);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8; ihdr[9] = 6; // 8-bit RGBA
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk("IHDR", ihdr), chunk("IDAT", deflateSync(raw)), chunk("IEND", Buffer.alloc(0)),
  ]);
}

const BLUE = [29, 78, 216, 255];
const WHITE = [255, 255, 255, 255];

function inTriangle(px, py, ax, ay, bx, by, cx, cy) {
  const d = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax);
  const l1 = ((bx - px) * (cy - py) - (by - py) * (cx - px)) / d;
  const l2 = ((cx - px) * (ay - py) - (cy - py) * (ax - px)) / d;
  const l3 = 1 - l1 - l2;
  return l1 >= 0 && l2 >= 0 && l3 >= 0;
}

function draw(size, { rounded }) {
  const buf = Buffer.alloc(size * size * 4);
  const R = rounded ? size * 0.22 : 0;
  const inRR = (x, y) => {
    if (!rounded) return true;
    const qx = Math.min(Math.max(x, R), size - R);
    const qy = Math.min(Math.max(y, R), size - R);
    const dx = x - qx, dy = y - qy;
    return dx * dx + dy * dy <= R * R || (x >= R && x <= size - R) || (y >= R && y <= size - R);
  };
  const t = 0.055 * size; // triangle stroke
  const ax = size / 2, ay = size * 0.30;
  const bx = size * 0.20, by = size * 0.74;
  const cx = size * 0.80, cy = size * 0.74;
  // Inner triangle (hole) inset
  const ix = size / 2, iy = size * 0.40;
  const ibx = size * 0.30, iby = size * 0.66;
  const icx = size * 0.70, icy = size * 0.66;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      let px = BLUE;
      if (inRR(x, y)) {
        const inOuter = inTriangle(x, y, ax, ay, bx, by, cx, cy);
        const inInner = inTriangle(x, y, ix, iy, ibx, iby, icx, icy);
        const barW = size * 0.035;
        const inBar = Math.abs(x - size / 2) < barW && y > size * 0.47 && y < size * 0.60;
        const dotR = size * 0.028;
        const inDot = (x - size / 2) ** 2 + (y - size * 0.655) ** 2 < dotR * dotR;
        if ((inOuter && !inInner) || inBar || inDot) px = WHITE;
      }
      const o = (y * size + x) * 4;
      buf[o] = px[0]; buf[o + 1] = px[1]; buf[o + 2] = px[2]; buf[o + 3] = px[3];
    }
  }
  return png(size, size, buf);
  void t;
}

writeFileSync(join(outDir, "icon-192.png"), draw(192, { rounded: true }));
writeFileSync(join(outDir, "icon-512.png"), draw(512, { rounded: true }));
writeFileSync(join(outDir, "icon-maskable-512.png"), draw(512, { rounded: false }));
console.log("icons written to public/icons/");
