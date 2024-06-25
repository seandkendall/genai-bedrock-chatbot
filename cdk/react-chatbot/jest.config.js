module.exports = {
  setupFilesAfterEnv: ['@testing-library/react/cleanup-after-each'],
  testEnvironment: 'jsdom',
  moduleNameMapper: {
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
  },
};
