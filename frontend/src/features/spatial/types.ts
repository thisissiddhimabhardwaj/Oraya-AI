export type Vec3 = { x: number; y: number; z: number };
export type Primitive =
  | "sphere"
  | "box"
  | "cylinder"
  | "cone"
  | "torus"
  | "line"
  | "curve"
  | "arrow"
  | "bond"
  | "particles";
export interface Animation {
  kind: "rotate" | "orbit" | "translate" | "pulse";
  axis: "x" | "y" | "z";
  duration: number;
  radius: number;
  target: Vec3;
  explanation: string;
}
export interface SceneObject {
  id: string;
  label: string;
  type: Primitive;
  position: Vec3;
  dimensions: Vec3;
  material: {
    color: string;
    opacity: number;
    roughness: number;
    metalness: number;
  };
  explanation: string;
  points: Vec3[];
  animation?: Animation | null;
  source_ids: string[];
}
export interface SceneSpec {
  version: 1;
  title: string;
  description: string;
  disclaimer: string;
  objectives: string[];
  camera: Vec3;
  objects: SceneObject[];
  connections: {
    source: string;
    target: string;
    label: string;
    explanation: string;
  }[];
  steps: {
    title: string;
    explanation: string;
    object_ids: string[];
    camera?: Vec3 | null;
  }[];
  challenges: { id: string; kind: string; prompt: string; options: string[] }[];
}
