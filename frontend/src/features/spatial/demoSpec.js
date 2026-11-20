export function demoSpec(e) {
  return {
    version: 1,
    title: e.title,
    description: e.intro,
    disclaimer:
      "Optional predefined demonstration. Not an AI-generated environment.",
    objectives: [e.subtitle],
    camera: { x: 8, y: 7, z: 12 },
    objects: e.objects.map((o, i) => ({
      id: `demo-${i}`,
      label: o[0],
      explanation: o[1],
      type: e.shape === "box" ? "box" : "sphere",
      position: { x: o[2], y: o[3], z: o[4] },
      dimensions: { x: o[5] * 2, y: o[5] * 2, z: o[5] * 2 },
      material: {
        color: o[6],
        opacity: e.subtitle === "Animal cell" && i === 0 ? 0.2 : 1,
        roughness: 0.6,
        metalness: 0,
      },
      source_ids: [],
    })),
    connections: (e.bonds || []).map(([a, b]) => ({
      source: `demo-${a}`,
      target: `demo-${b}`,
      label: "Connection",
      explanation: "Schematic connection shown by this demonstration.",
    })),
    steps: e.steps.map((title) => ({
      title,
      explanation: title,
      object_ids: ["demo-0"],
    })),
    challenges: [],
  };
}
