'use strict';
window.DoceDocuments={
 async generate(order,state,kitchen=false,share=false){
  const {jsPDF}=window.jspdf,L=window.DoceLogic,doc=new jsPDF({unit:'mm',format:'a4'}),width=180;let y=18;
  const ink=[42,61,73],coral=[190,103,80];doc.setTextColor(...ink);
  function space(height){if(y+height>275){doc.addPage();y=18;}}
  function text(value,size=10,bold=false){doc.setFont('helvetica',bold?'bold':'normal');doc.setFontSize(size);const lines=doc.splitTextToSize(String(value||''),width);for(const line of lines){space(size*.5+2);doc.text(line,15,y);y+=size*.5+1;}y+=2;}
  function photo(id,maxW=60,maxH=42){const source=state.images[id];if(!source)return;try{const info=doc.getImageProperties(source),ratio=Math.min(maxW/info.width,maxH/info.height),w=info.width*ratio,h=info.height*ratio;space(h+7);doc.addImage(source,source.startsWith('data:image/png')?'PNG':'JPEG',15,y,w,h);y+=h+6;}catch(ignored){text('Referência de imagem indisponível.',8);}}
  function lineDetails(line){const pieces=[line.name+(line.gift?' [BRINDE]':'')];if(line.fillings.length)pieces.push('Recheios: '+line.fillings.join(', '));if(line.brigadeiro_type)pieces.push(line.brigadeiro_type+' · '+(line.split?'50/50: ':'Sabor: ')+line.flavors.join(' / '));if(line.composition.length)pieces.push('Composição por kit: '+line.composition.join('; '));for(const extra of line.extras){pieces.push('Adicional: '+extra.quantity+' x '+extra.name+(line.gift||extra.gift?' [BRINDE]':kitchen?'':' · '+L.money(extra.amount_cents)));if(extra.flavors?.length)pieces.push(extra.brigadeiro_type+': '+extra.flavors.join(' / '));if(extra.personalization)pieces.push('Personalização: '+extra.personalization);}if(line.details)pieces.push('Detalhes: '+line.details);if(line.negotiation?.notes)pieces.push('Exceção autorizada: '+line.negotiation.notes);return pieces.join('\n');}
  photo(order.shop.logo,44,20);doc.setTextColor(...coral);text(order.shop.name,21,true);doc.setTextColor(...ink);
  text([order.shop.phone,order.shop.document].filter(Boolean).join(' · '),9);if(order.shop.address)text(order.shop.address,9);
  y+=4;text((kitchen?'FICHA DE PRODUÇÃO':'ORÇAMENTO')+' #'+String(order.number).padStart(4,'0'),15,true);
  text('Cliente: '+order.customer.name+' · WhatsApp: '+order.customer.phone,10);
  text('Saída / retirada: '+order.event_date.split('-').reverse().join('/')+' às '+order.event_time+' · '+order.fulfillment,10);
  text('Endereço: '+(order.fulfillment==='Entrega'?order.delivery_address:'Retirada na loja'),9);
  if(kitchen){for(const line of order.lines){y+=3;text(String(line.quantity).replace('.',',')+' '+line.unit+' · '+line.name,12,true);text(lineDetails(line),10);photo(line.reference_photo);for(const extra of line.extras)if(extra.reference_photo){text('Inspiração: '+extra.name,9,true);photo(extra.reference_photo);}}text('DECORAÇÃO, ALERGIAS E TRANSPORTE',12,true);text(order.production_notes||'Nenhuma orientação registrada.');y+=4;text('CONFERÊNCIA',12,true);text('Produzido por: ____________________');text('Conferido por: ____________________');}
  else{
   text('CPF: '+(order.customer.cpf||'Não informado'),9);text('Válido até: '+order.valid_until.split('-').reverse().join('/')+' · '+L.status(order),9);
   doc.autoTable({startY:y+3,margin:{left:15,right:15,top:16,bottom:18},head:[['Itens / sabores / adicionais','Qtd.','Unitário','Total']],body:order.lines.map(line=>[lineDetails(line),String(line.quantity).replace('.',',')+' '+line.unit,L.money(line.gift?0:line.unit_cents),L.money(line.total_cents)]),styles:{font:'helvetica',fontSize:8,cellPadding:3,overflow:'linebreak',valign:'top'},headStyles:{fillColor:[246,237,232],textColor:ink},columnStyles:{0:{cellWidth:105},1:{cellWidth:19},2:{cellWidth:28},3:{cellWidth:28}},theme:'grid'});
   y=doc.lastAutoTable.finalY+10;const t=order.totals;text('Subtotal: '+L.money(t.subtotal_cents),10);text('Desconto geral: '+L.money(t.discount_cents)+' · Frete: '+L.money(t.delivery_cents),10);text('Preço Cartão: '+L.money(t.card_cents),11,true);
   if(order.pix_enabled)text('Valor PIX/Dinheiro: '+L.money(t.total_cents)+' · Desconto ativado: '+order.pix_percent+'%',11,true);
   text('Total acordado ('+order.payment_method+'): '+L.money(t.total_cents),13,true);text('Sinal mínimo (50%): '+L.money(t.deposit_cents));text('Recebido: '+L.money(L.paid(order))+' · Saldo devedor: '+L.money(t.total_cents-L.paid(order)));
   y+=3;text('OBSERVAÇÕES GERAIS',11,true);text(order.notes||'Nenhuma observação registrada.');text('DECORAÇÃO / ALERGIAS / TRANSPORTE',11,true);text(order.production_notes||'Nenhuma orientação registrada.');y+=4;
   text('A data e produção só estarão garantidas mediante entrada de 50%. Em caso de desistência, o valor da entrada não será devolvido (Artigos 417 a 420 do Código Civil). Alterações no pedido aceitas até '+order.shop.change_days+' dias antes do evento.',8);
  }
  const pages=doc.getNumberOfPages();for(let page=1;page<=pages;page++){doc.setPage(page);doc.setDrawColor(...coral);doc.line(15,282,195,282);doc.setFontSize(8);doc.setTextColor(...ink);doc.text(kitchen?'Ficha interna de produção':'Orçamento · Conserve uma cópia deste documento',15,287);doc.text('Página '+page+' de '+pages,195,287,{align:'right'});}
  const name=(kitchen?'producao-':'orcamento-')+String(order.number).padStart(4,'0')+'.pdf';
  if(window.Android){const data=doc.output('datauristring');if(share)Android.sharePdf(data,name);else Android.savePdf(data,name);}else doc.save(name);
 }
};
