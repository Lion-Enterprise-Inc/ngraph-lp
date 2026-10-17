// next/image の代わり。public/ の画像は /cases/_assets/ に置く
export default function Image({ src, alt, width, height, className }: { src: string; alt: string; width?: number; height?: number; className?: string }) {
  const s = typeof src === "string" && src.startsWith("/") ? `/cases/_assets${src}` : src;
  return <img src={s} alt={alt} width={width} height={height} className={className} />;
}
