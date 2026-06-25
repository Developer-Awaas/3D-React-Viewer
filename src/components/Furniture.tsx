// All furniture here is built from primitives (boxes/cylinders/spheres) — no
// downloads. The realistic sofa is a separate loaded GLTF model (see Model.tsx).

function Rug() {
  return (
    <mesh position={[0, 0.012, 0.3]} receiveShadow>
      <boxGeometry args={[2.6, 0.02, 1.7]} />
      <meshStandardMaterial color="#7a3b3b" roughness={0.9} />
    </mesh>
  )
}

function CoffeeTable() {
  const legX = 0.5, legZ = 0.32
  const legs: [number, number, number][] = [
    [-legX, 0.2, 0.3 - legZ], [legX, 0.2, 0.3 - legZ],
    [-legX, 0.2, 0.3 + legZ], [legX, 0.2, 0.3 + legZ],
  ]
  return (
    <group>
      {/* table top */}
      <mesh position={[0, 0.42, 0.3]} castShadow receiveShadow>
        <boxGeometry args={[1.2, 0.06, 0.8]} />
        <meshStandardMaterial color="#5b3a21" roughness={0.5} />
      </mesh>
      {/* four legs */}
      {legs.map((p, i) => (
        <mesh key={i} position={p} castShadow>
          <boxGeometry args={[0.08, 0.4, 0.08]} />
          <meshStandardMaterial color="#3f2815" roughness={0.6} />
        </mesh>
      ))}
    </group>
  )
}

function Plant() {
  return (
    <group position={[1.9, 0, -1.9]}>
      {/* pot */}
      <mesh position={[0, 0.2, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.18, 0.13, 0.4, 16]} />
        <meshStandardMaterial color="#9c5b3b" roughness={0.8} />
      </mesh>
      {/* foliage */}
      <mesh position={[0, 0.6, 0]} castShadow>
        <sphereGeometry args={[0.32, 16, 16]} />
        <meshStandardMaterial color="#3f7d3f" roughness={1} />
      </mesh>
    </group>
  )
}

export default function Furniture() {
  return (
    <group>
      <Rug />
      <CoffeeTable />
      <Plant />
    </group>
  )
}
