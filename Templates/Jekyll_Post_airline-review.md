<%*
  let title = await tp.system.prompt("파일명 입력 (영문 소문자, 예: ke411-review)");
  await tp.file.rename(tp.date.now("YYYY-MM-DD") + "-" + title);
_%>
---
layout: post
title: "[탑승기] "
date: <% tp.date.now("YYYY-MM-DD HH:mm:ss") %> +0900
category: airline-review
tags:
  - 항공권
  - 
series: 
image: /assets/images/airline-review/
---

