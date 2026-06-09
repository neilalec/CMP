module.exports = function transformImportMetaEnv({ types: t }) {
  const isImportMeta = (node) => (
    t.isMetaProperty(node)
    && node.meta.name === 'import'
    && node.property.name === 'meta'
  );

  const isImportMetaEnv = (node) => (
    t.isMemberExpression(node)
    && isImportMeta(node.object)
    && t.isIdentifier(node.property, { name: 'env' })
  );

  const processEnvMember = (name) => (
    t.memberExpression(
      t.memberExpression(t.identifier('process'), t.identifier('env')),
      t.identifier(name)
    )
  );

  return {
    name: 'transform-import-meta-env-for-jest',
    visitor: {
      MemberExpression(path) {
        const { node } = path;

        if (isImportMetaEnv(node)) {
          path.replaceWith(processEnvMember('NODE_ENV'));
          return;
        }

        if (!isImportMetaEnv(node.object)) {
          return;
        }

        const envKey = node.computed && t.isStringLiteral(node.property)
          ? node.property.value
          : node.property.name;

        if (envKey === 'DEV') {
          path.replaceWith(
            t.binaryExpression('!==', processEnvMember('NODE_ENV'), t.stringLiteral('production'))
          );
          return;
        }

        if (envKey === 'PROD') {
          path.replaceWith(
            t.binaryExpression('===', processEnvMember('NODE_ENV'), t.stringLiteral('production'))
          );
          return;
        }

        path.replaceWith(processEnvMember(envKey));
      }
    }
  };
};
