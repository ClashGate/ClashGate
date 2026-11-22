// Panel state and actions for the home page inbound list and add-node form.
// Split out of usePanel.js: `p` carries the shared state and helpers usePanel creates first.
import { reactive, computed, watch } from 'vue'
import { t } from '../i18n.js'

export function useInbounds(p) {
  const { busyKey, openConfirmDialog, postAction } = p

  const PROTOCOLS = [
    {
      value: 'vless-reality',
      label: 'VLESS Reality',
      defaultName: 'VlessReality',
      desc: '免证书的新一代协议',
      lockedNote: '已锁定安全默认：默认启用 VLESS Encryption (vless-x25519)。SNI 可自填，留空从内置域名池随机抽取',
    },
    {
      value: 'hysteria2',
      label: 'Hysteria2',
      defaultName: 'Hysteria2',
      desc: '新一代 UDP 协议',
      lockedNote: '已锁定安全默认：混淆密码 (Salamander) 默认随机生成，不可手动关闭',
    },
    {
      value: 'shadowsocks',
      label: 'Shadowsocks',
      defaultName: 'Shadowsocks',
      desc: '经典轻量级加密协议，默认锁定 aes-256-gcm',
      lockedNote: '已锁定安全默认：加密算法固定为 aes-256-gcm，密码自动随机生成',
    },
    {
      value: 'snell',
      label: 'Snell V6',
      defaultName: 'SnellV6',
      desc: '轻量高效的私有协议，内置基于 PSK 的流量整形',
      lockedNote: '已锁定安全默认：PSK 自动随机生成，流量整形使用 v6 默认模式',
    },
    {
      value: 'anytls',
      label: 'AnyTLS',
      defaultName: 'AnyTLS',
      desc: '内置随机填充与随机指纹的新一代 TLS 协议',
      lockedNote: '已锁定安全默认：客户端 TLS 指纹与长度填充策略均自动随机生成',
    },
    {
      value: 'shadowquic',
      label: 'ShadowQUIC',
      defaultName: 'ShadowQUIC',
      desc: '免证书的新一代 QUIC 协议，内置随机 JLS 伪装',
      lockedNote: '已锁定安全默认：伪装地址 (JLS) 可自填，留空从内置域名池随机抽取，拥塞控制默认 bbr',
    },
    {
      value: 'sudoku',
      label: 'Sudoku',
      defaultName: 'Sudoku',
      desc: '基于数独流量特征变换与 chacha20 加密的抗审查协议',
      lockedNote: '已锁定安全默认：AEAD 加密固定为 chacha20-poly1305，密钥对自动生成',
    },
    {
      value: 'tuic',
      label: 'TUIC v5',
      defaultName: 'TUICv5',
      desc: '基于 QUIC 的低延迟零握手机制 UDP 协议',
      lockedNote: '已启用安全默认：UUID 与密码随机生成，开启 0-RTT 与 native UDP 转发',
    },
    {
      value: 'trusttunnel',
      label: 'TrustTunnel',
      defaultName: 'TrustTunnel',
      desc: '基于标准 HTTP/2 与 HTTP/3 的高隐蔽 TLS 隧道协议',
      lockedNote: '已启用安全默认：强随机密码与 TLS 证书加密传输',
    },
    {
      value: 'mieru',
      label: 'Mieru',
      defaultName: 'Mieru',
      desc: '抗深度包检测（DPI）的混淆传输代理协议',
      lockedNote: '已启用安全默认：强随机密码与抗 DPI 流量混淆',
    },
    {
      value: 'http',
      label: 'HTTP',
      defaultName: 'HTTP',
      desc: '通用 HTTP / HTTPS 代理协议',
      lockedNote: '已启用安全默认：鉴权密码自动随机生成',
    },
    {
      value: 'socks',
      label: 'SOCKS5',
      defaultName: 'SOCKS5',
      desc: '通用 SOCKS5 代理协议，支持 UDP 转发',
      lockedNote: '已启用安全默认：鉴权密码自动随机生成，默认开启 UDP',
    },
  ]

  const DEFAULT_NAMES = Object.fromEntries(PROTOCOLS.map((p) => [p.value, p.defaultName]))
  const PROTOCOL_MAP = Object.fromEntries(PROTOCOLS.map((p) => [p.value, p]))

  const inboundForm = reactive({
    kind: 'vless-reality',
    name: 'VlessReality',
    port: '',
    tuic_cc: 'bbr',
    tt_cc: 'bbr',
    mieru_transport: 'TCP',
    http_tls: '0',
    socks_tls: '0',
    sni: '',
  })

  const currentProtocol = computed(() => PROTOCOL_MAP[inboundForm.kind] || PROTOCOLS[0])
  const currentDefaultName = computed(() => DEFAULT_NAMES[inboundForm.kind] || 'VlessReality')
  // Protocols that show one extra option field (SNI or a select) in the add-node form.
  const PROTOCOL_HAS_OPTION = new Set(['vless-reality', 'shadowquic', 'tuic', 'trusttunnel', 'mieru', 'http', 'socks'])
  const sniEditable = computed(() =>
    inboundForm.kind === 'vless-reality' || inboundForm.kind === 'shadowquic'
  )

  watch(
    () => inboundForm.kind,
    (newKind, oldKind) => {
      const oldDefault = DEFAULT_NAMES[oldKind] || ''
      const newDefault = DEFAULT_NAMES[newKind] || newKind
      if (!inboundForm.name.trim() || inboundForm.name.trim() === oldDefault) {
        inboundForm.name = newDefault
      }
    }
  )

  let pendingAddReqId = ''

  async function submitAddInbound() {
    if (busyKey.value) return
    if (!pendingAddReqId) {
      pendingAddReqId = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    }
    const payload = {
      kind: inboundForm.kind,
      name: inboundForm.name.trim() || currentDefaultName.value,
      port: inboundForm.port.trim(),
      tuic_cc: inboundForm.tuic_cc,
      tt_cc: inboundForm.tt_cc,
      mieru_transport: inboundForm.mieru_transport,
      http_tls: inboundForm.http_tls,
      socks_tls: inboundForm.socks_tls,
      sni: sniEditable.value ? inboundForm.sni.trim() : '',
      req_id: pendingAddReqId,
    }
    const res = await postAction('/inbounds/add', payload, 'add-inbound')
    // No answer (timeout / dropped connection): keep the id so a retry is not added twice.
    if (res) pendingAddReqId = ''
    if (res && res.ok) {
      inboundForm.port = ''
      inboundForm.sni = ''
      inboundForm.name = currentDefaultName.value
    }
  }

  function resetInboundPassword(item) {
    if (!item || !item.reset_url) return
    openConfirmDialog({
      title: t('重置密码'),
      message: t('确定重置节点「{name}」的密码？点顶部「应用配置」后生效，客户端需要重新更新订阅。', { name: item.name }),
      confirmText: t('确认重置'),
      tone: 'amber',
      onConfirm: () => postAction(item.reset_url, {}, `rst-${item.key}`),
    })
  }

  function deleteInbound(item) {
    if (!item || !item.delete_url) return
    openConfirmDialog({
      title: t('删除节点'),
      message: t('确定删除节点「{name}」？点顶部「应用配置」后生效。', { name: item.name }),
      confirmText: t('确认删除'),
      tone: 'rose',
      onConfirm: () => postAction(item.delete_url, {}, `del-${item.key}`),
    })
  }

  return {
    PROTOCOLS,
    DEFAULT_NAMES,
    PROTOCOL_MAP,
    inboundForm,
    currentProtocol,
    currentDefaultName,
    PROTOCOL_HAS_OPTION,
    sniEditable,
    pendingAddReqId,
    submitAddInbound,
    resetInboundPassword,
    deleteInbound,
  }
}
