import { describe, it, expect } from "bun:test";
import { haversineKm, nearestProvince, type ProvincePoint } from "./nearest";

const PROVINCES: ProvincePoint[] = [
  { id: 1, name_th: "กรุงเทพมหานคร", name_en: "Bangkok", lat: 13.7563, lon: 100.5018 },
  { id: 2, name_th: "เชียงใหม่", name_en: "Chiang Mai", lat: 18.7883, lon: 98.9853 },
  { id: 3, name_th: "ภูเก็ต", name_en: "Phuket", lat: 7.8804, lon: 98.3923 },
  // string coords (postgres numeric arrives as string)
  { id: 4, name_th: "ขอนแก่น", name_en: "Khon Kaen", lat: "16.4419", lon: "102.8360" },
];

describe("haversineKm", () => {
  it("is ~0 for identical points", () => {
    expect(haversineKm(13.75, 100.5, 13.75, 100.5)).toBeLessThan(0.001);
  });

  it("matches a known distance (Bangkok→Chiang Mai ≈ 580 km)", () => {
    const d = haversineKm(13.7563, 100.5018, 18.7883, 98.9853);
    expect(d).toBeGreaterThan(560);
    expect(d).toBeLessThan(600);
  });
});

describe("nearestProvince", () => {
  it("returns the closest province", () => {
    // Near Bangkok
    expect(nearestProvince(13.8, 100.6, PROVINCES)?.id).toBe(1);
    // Near Chiang Mai
    expect(nearestProvince(18.7, 99.0, PROVINCES)?.id).toBe(2);
    // Near Phuket
    expect(nearestProvince(8.0, 98.3, PROVINCES)?.id).toBe(3);
  });

  it("handles string coordinates", () => {
    expect(nearestProvince(16.4, 102.8, PROVINCES)?.id).toBe(4);
  });

  it("returns null for an empty list", () => {
    expect(nearestProvince(13.8, 100.6, [])).toBeNull();
  });

  it("skips provinces with non-finite coordinates", () => {
    const bad: ProvincePoint[] = [
      { id: 9, name_th: "x", name_en: "x", lat: NaN, lon: NaN },
      { id: 1, name_th: "Bangkok", name_en: "Bangkok", lat: 13.7563, lon: 100.5018 },
    ];
    expect(nearestProvince(13.8, 100.6, bad)?.id).toBe(1);
  });
});
