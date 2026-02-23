<%*
  let title = await tp.system.prompt("파일명 입력 (영문 소문자, 예: japan-visa-tips)");
  await tp.file.rename(tp.date.now("YYYY-MM-DD") + "-" + title);
_%>
---
layout: post
title: "[꿀팁] "
date: <% tp.date.now("YYYY-MM-DD HH:mm:ss") %> +0900
category: tips
tags:
  - 여행팁
  - 
image: /assets/images/tips/
---
