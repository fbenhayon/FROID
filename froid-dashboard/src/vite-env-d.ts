declare const importMeta: { env: { [key: string]: string } };

declare module "*.css?raw" {
  const content: string;
  export default content;
}

declare module "*.html?raw" {
  const content: string;
  export default content;
}
