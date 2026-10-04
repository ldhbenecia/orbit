export const ruleName = (spec: string) => {
  const [name, arg] = spec.split("-");
  if (name === "hold") return "단순 보유";
  if (name === "ma") return `${arg}일선 규칙`;
  if (name === "vb") return `변동성 돌파 (k ${arg})`;
  return spec;
};
