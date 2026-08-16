# 글에 들어간 사진에 width/height 를 자동으로 붙인다.
#
# 크기가 없으면 브라우저가 사진 자리를 미리 잡지 못해, 사진이 로드될 때마다
# 아래 글이 밀린다(CLS). 구글 Core Web Vitals 감점 항목이라 검색 순위에 영향이 있다.
#
# 마크다운을 고치지 않고 빌드 시점에 붙이므로, 앞으로 쓰는 글도 자동으로 적용된다.
# 외부 젬 없이 파일 헤더에서 직접 크기를 읽는다(WebP·JPEG·PNG).

module ImgSize
  CACHE = {}

  def self.size(path)
    return CACHE[path] if CACHE.key?(path)
    CACHE[path] = read(path)
  end

  def self.read(path)
    return nil unless File.file?(path)
    File.open(path, 'rb') do |f|
      head = f.read(32) or return nil
      return webp(f, head) if head[0, 4] == 'RIFF' && head[8, 4] == 'WEBP'
      return png(head)    if head[0, 8] == "\x89PNG\r\n\x1A\n".b
      return jpeg(f)      if head[0, 2] == "\xFF\xD8".b
      nil
    end
  rescue StandardError
    nil
  end

  # WebP 는 세 가지 형식이 있어 각각 다른 위치에서 읽는다
  def self.webp(f, head)
    case head[12, 4]
    when 'VP8 '                                   # 손실 압축
      f.seek(26); d = f.read(4)
      [d[0, 2].unpack1('v') & 0x3FFF, d[2, 2].unpack1('v') & 0x3FFF]
    when 'VP8L'                                   # 무손실
      f.seek(21); b = f.read(4).unpack('C4')
      [((b[1] & 0x3F) << 8 | b[0]) + 1,
       ((b[3] & 0x0F) << 10 | b[2] << 2 | (b[1] & 0xC0) >> 6) + 1]
    when 'VP8X'                                   # 확장 (애니메이션 등)
      f.seek(24); b = f.read(6).unpack('C6')
      [(b[2] << 16 | b[1] << 8 | b[0]) + 1,
       (b[5] << 16 | b[4] << 8 | b[3]) + 1]
    end
  end

  def self.png(head)
    [head[16, 4].unpack1('N'), head[20, 4].unpack1('N')]
  end

  def self.jpeg(f)
    f.seek(2)
    while (marker = f.read(2))
      break unless marker[0] == "\xFF".b
      code = marker[1].unpack1('C')
      len = f.read(2).unpack1('n')
      # SOF0~SOF15 (DHT/DAC/RST 제외) 에 크기가 들어 있다
      if code >= 0xC0 && code <= 0xCF && ![0xC4, 0xC8, 0xCC].include?(code)
        f.read(1)
        return f.read(4).unpack('n2').reverse
      end
      f.seek(len - 2, IO::SEEK_CUR)
    end
    nil
  end
end

Jekyll::Hooks.register [:posts, :documents, :pages], :post_render do |item|
  next unless item.output_ext == '.html'
  next unless item.output.include?('<img ')

  item.output = item.output.gsub(/<img\s([^>]*?)src="(\/[^"]+)"([^>]*?)>/) do
    before, src, after = Regexp.last_match(1), Regexp.last_match(2), Regexp.last_match(3)
    tag = "<img #{before}src=\"#{src}\"#{after}>"
    # 이미 지정돼 있으면 건드리지 않는다
    next tag if tag =~ /\swidth=/ || tag =~ /\sheight=/

    dim = ImgSize.size(File.join(item.site.source, src))
    next tag unless dim

    # 자기닫힘(<img ... />) 이면 슬래시를 떼고 뒤에 다시 붙인다.
    # 안 그러면 alt="..." / width="1200" 처럼 슬래시가 중간에 끼어 태그가 어긋난다.
    rest = after.sub(/\s*\/\s*\z/, '')
    close = after =~ /\/\s*\z/ ? ' /' : ''
    "<img #{before}src=\"#{src}\"#{rest} width=\"#{dim[0]}\" height=\"#{dim[1]}\"#{close}>"
  end
end
