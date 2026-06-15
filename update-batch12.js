const fs = require('fs');

const data = JSON.parse(fs.readFileSync('.understand-anything/intermediate/batch-12.json', 'utf8'));

const functionSummaries = {
    'fetchTtsProviders': '获取支持的文本转语音 (TTS) 平台服务商列表。',
    'fetchTtsSettings': '获取当前全局或应用的文本转语音配置参数。',
    'updateTtsSettings': '更新系统的文本转语音设置，如音量和语速。',
    'testPlatformTts': '调用指定平台的 TTS 接口进行语音合成测试。',
    'fetchCompanyTtsOptions': '获取特定租户/公司的专属 TTS 音色和配置选项。',
    'updateCompanyDefaultTtsVoice': '设置并更新公司的默认文本转语音音色。',
    'testCompanyTts': '使用公司特定的配置参数测试语音合成功能。',
    'TtsManagementPage': '渲染文本转语音 (TTS) 音色模型管理页面，支持配置和测试不同服务商的语音能力。',
    'TtsSettingsPage': '渲染文本转语音的应用级配置页面，允许调整默认音量、语速及首选音色。'
};

data.nodes.forEach(node => {
    if (node.type === 'function' && functionSummaries[node.name]) {
        node.summary = functionSummaries[node.name];
        node.tags = ['api-handler', 'tts'];
        if (node.name.includes('Page')) {
            node.tags = ['component', 'view', 'tts'];
        }
    }
});

fs.writeFileSync('.understand-anything/intermediate/batch-12.json', JSON.stringify(data, null, 2), 'utf8');