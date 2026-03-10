module.exports = {
    testEnvironment: 'jsdom',
    setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
    moduleNameMapper: {
        '\\.(css|less|scss|sass)$': '<rootDir>/src/__mocks__/styleMock.js',
        '\\.(gif|ttf|eot|svg|png)$': '<rootDir>/src/__mocks__/fileMock.js',
    },
    transformIgnorePatterns: [
        'node_modules/(?!(axios|react-markdown|remark-gfm|remark-math|rehype-katex|unified|bail|devlop|is-plain-obj|trough|vfile|unist-util-stringify-position|micromark|mdast-util-from-markdown|mdast-util-to-string|mdast-util-gfm|mdast-util-gfm-autolink-literal|mdast-util-gfm-footnote|mdast-util-gfm-strikethrough|mdast-util-gfm-table|mdast-util-gfm-task-list-item|mdast-util-find-and-replace|escape-string-regexp|mdast-util-phrasing|mdast-util-math|micromark-extension-gfm|micromark-extension-gfm-autolink-literal|micromark-extension-gfm-footnote|micromark-extension-gfm-strikethrough|micromark-extension-gfm-table|micromark-extension-gfm-tagfilter|micromark-extension-gfm-task-list-item|micromark-extension-math|micromark-util-combine-extensions|micromark-util-chunked|micromark-util-character|micromark-util-encode|micromark-util-sanitize-uri|micromark-util-decode-numeric-character-reference|micromark-util-decode-string|micromark-util-normalize-identifier|micromark-util-types|micromark-util-resolve-all|micromark-util-subtokenize|micromark-util-classify-character|micromark-util-events-to-acorn|micromark-factory-space|micromark-factory-whitespace|micromark-factory-label|micromark-factory-title|micromark-factory-destination|micromark-factory-mdx-expression|ccount|mdast-util-to-hast|trim-lines|unist-util-position|unist-util-visit|unist-util-is|unist-util-generated|unist-util-visit-parents|hast-util-whitespace|property-information|space-separated-tokens|comma-separated-tokens|hast-util-to-jsx-runtime|estree-util-is-identifier-name|hast-util-from-parse5|hastscript|web-namespaces|zwitch|html-void-elements|rehype-parse|hast-util-from-html|rehype-katex|hast-util-to-text|hast-util-has-property|hast-util-is-element)/)'
    ],
};
