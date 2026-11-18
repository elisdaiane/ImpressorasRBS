# Relatório funcional da aplicação

## 1. Resumo

O **Monitor de Impressoras** é uma aplicação web interna para acompanhar impressoras de rede, consultar níveis de suprimentos, administrar o estoque de toners e conferir relatórios mensais PRINTER. O servidor foi desenvolvido em Python com Flask; a interface usa HTML, CSS e JavaScript; os dados operacionais são mantidos principalmente em SQLite, com o cadastro de impressoras em planilhas Excel.

Este relatório descreve o comportamento identificado no código e nos testes existentes. Ele não confirma que impressoras, envio de e-mail ou configurações externas estejam funcionando no ambiente de execução.

## 2. Componentes e responsabilidades

| Componente | Responsabilidade |
|---|---|
| [`app.py`](./app.py) | Servidor Flask, autenticação, permissões, rotas da interface e APIs, atualização do painel e integração entre os módulos. |
| [`estoque.py`](./estoque.py) | Banco SQLite: cadastro de toner, saldos, movimentações, trocas, níveis lidos por SNMP e eventos de indisponibilidade. |
| [`suprimentos_snmp.py`](./suprimentos_snmp.py) | Consulta de impressoras por SNMP, leitura de suprimentos/contador, detecção de indisponibilidade, alertas e atualização dos dados de monitoramento. |
| [`relatorio_printer.py`](./relatorio_printer.py) | Leitura de PDFs PRINTER, extração de equipamentos, comparação com o cadastro e geração do texto de e-mail. |
| [`templates/`](./templates) e [`static/`](./static) | Páginas HTML, estilos e interações da interface. A tela principal fica em [`templates/index.html`](./templates/index.html); a lógica do navegador está em [`static/js/script.js`](./static/js/script.js). |
| [`tests/`](./tests) | Testes de autenticação, cadastro de impressoras, grupos, estoque mínimo e análise/aprovação de relatórios. |

## 3. Funcionalidades

### 3.1 Acesso e administração de usuários

- Login com usuário e senha; as senhas são guardadas como hash.
- Primeiro acesso de contas individuais por convite de uso único, com expiração em 48 horas. A pessoa define o próprio usuário e senha ao aceitar o convite.
- A opção de administração de contas foi retirada do menu; a rota administrativa existente continua restrita a administradores e mantém os usuários e permissões cadastrados.
- A presença é atualizada durante o uso do painel; a tela de administração considera online quem acessou nos últimos dois minutos.
- Permissões separadas para monitoramento, edição/exclusão de impressoras, visualização e operações de estoque, histórico e análise/aprovação de relatórios. A administração tem acesso total.
- Há proteção CSRF em formulários, tokens temporários para login/recuperação e redefinição da senha administrativa limitada ao próprio computador.
- O acesso é limitado a loopback ou endereços privados; `PAINEL_REDE_LOCAL` pode restringir a sub-rede permitida.

### 3.2 Monitoramento das impressoras

- O cadastro vem de `ImpressorasRBS_atualizada.xlsx` quando esse arquivo existe; caso contrário, usa `ImpressorasRBS.xlsx`.
- O painel consulta `/dados` e atualiza os indicadores a cada 30 segundos. O servidor mantém um cache e inicia a coleta SNMP em segundo plano, também com intervalo mínimo de 30 segundos.
- A coleta combina IPs do cadastro com IPs encontrados em coletas anteriores e consulta as impressoras por SNMP na porta UDP 161.
- Quando a consulta de suprimentos falha, o monitor verifica novamente a presença por SNMP antes de marcar o equipamento como offline. Se ele responder, mas não fornecer os suprimentos, permanece online com os níveis indisponíveis. O estado offline indica ausência de resposta SNMP, não necessariamente que a impressora esteja desligada.
- Para impressoras que respondem, tenta identificar modelo e suprimentos e calcula níveis aproximados de toner a partir de capacidade e nível reportados pelo equipamento.
- A interface mostra total, online, offline e impressoras com toner baixo; apresenta gráficos de situação e quantidade por setor; permite pesquisar por nome/IP/patrimônio e filtrar por setor ou estado.
- A tela de impressoras organiza equipamentos por setor e oferece ficha com dados do equipamento, toners compatíveis cadastrados e contador de páginas consultado via SNMP.
- Na ficha, os toners são consultados independentemente do contador. A compatibilidade usa o modelo ou família cadastrada; o contador depende da resposta SNMP da impressora e informa quando está indisponível.
- Em **Relatório de impressões**, o sistema compara o contador registrado no dia 1 com o do dia 1 seguinte e permite baixar o resultado em Excel. A coleta começa à meia-noite, somente com a aplicação ligada, e equipamentos sem resposta são consultados novamente a cada 30 minutos durante o dia 1. Leituras ausentes não são estimadas; os horários efetivos e situações que precisam de conferência são exibidos. A diferença corresponde ao intervalo entre as leituras e pode não detectar reinicializações intermediárias do contador.
- Nas Kyocera TASKalfa coloridas compatíveis, a coleta consulta também a interface local do equipamento para P&B e níveis 1, 2 e 3 de cor; cada categoria soma cópias e impressões e não inclui fax. Esses contadores são independentes do contador geral SNMP e podem divergir dele. Modelos sem suporte ou leituras ausentes não recebem valores estimados. Para acessar o HTTPS dessas impressoras, que usam certificados próprios, a consulta não valida o certificado; não são enviadas credenciais e redirecionamentos são recusados.
- Há edição de nome/local, setor, série e modelo. Exclusão pelo painel marca o registro como excluído em vez de apagar a linha da planilha. O sistema impede editar ou excluir quando não consegue identificar o registro de forma única e mantém modelos M2040dn no grupo `OUTRAS`.

### 3.3 Alertas e histórico de toner baixo

- O cartão e a lista de toner baixo consideram impressoras online com pelo menos uma leitura confiável de **7% ou menos**. Leituras não confiáveis são excluídas, exceto estimativas identificadas; quando não é possível verificá-las, o cartão mostra um traço e a lista informa a falha. O envio automático de e-mail ocorre quando uma leitura confiável chega a **5% ou menos**, uma vez por impressora e cor enquanto permanecer nesse nível.
- O alerta usa configurações de destinatário e conta de e-mail presentes no ambiente; o envio não é tentado se remetente ou senha de aplicativo não estiverem configurados.
- Os alertas de toner usam destinatários fixos definidos no ambiente: `EMAIL_SEMED` para SEMED e `EMAIL_OUTROS` para os demais setores. A planilha de impressoras não é consultada para obter endereços de e-mail.
- Os alertas enviados são controlados em `alertas_enviados.json`; quando o nível volta a ser maior que 5%, um novo alerta pode ser enviado se cair novamente. Alertas registrados pela regra anterior permanecem ativos até o nível ultrapassar 5%, evitando repetição. Falhas de envio são registradas e retentadas na próxima coleta. Se ocorrer falha após o aceite do e-mail pelo servidor ou interrupção antes de gravar o controle, pode ocorrer envio duplicado.
- Leituras diárias em 6% são registradas em `historico_toner_6.json`. Cinco dias consecutivos nessa condição, com leitura atual ainda em 6%, classificam o toner como não confiável e suspendem o alerta automático. A interface tem uma seção própria para essa condição.
- Os toners sem chip das impressoras 10.52.0.6 (preto) e 10.6.0.1 (preto, ciano, magenta e amarelo) são classificados diretamente como não confiáveis. As leituras do chip são ignoradas e não provocam saída automática nem e-mail.
- Ao instalar um toner novo nesses equipamentos, use **Registrar saída**, informe uma unidade e marque a opção de troca sem chip. A saída e a troca são gravadas juntas depois da leitura do contador; se a leitura falhar, nenhuma das duas é gravada. O modelo e o patrimônio precisam corresponder ao cadastro. Não marque a opção para uma retirada que ainda não foi instalada.
- A primeira troca inicia o acompanhamento; após a troca seguinte, a média de páginas entre trocas é calculada separadamente por equipamento, cor e toner cadastrado. O nível é estimado considerando o toner recém-instalado como 100% e o consumo proporcional à média, limitado entre 0% e 100%. Antes de existir um ciclo completo, após falha do contador ou se o contador diminuir, o nível fica indisponível. Ciclos com contador reiniciado ou incompatível não entram na média. O painel identifica os valores como estimativas e não envia e-mails para eles.
- O contador utilizado é o contador geral de páginas: especialmente para cores, ele não mede a cobertura ou o consumo real de cada toner, portanto a estimativa pode divergir bastante da quantidade restante. A troca deve ser registrada no momento da instalação para que o ciclo seja representativo.
- O módulo de estoque também detecta uma possível troca quando o nível passa de até 10% para pelo menos 90%. Ele usa o modelo cadastrado da impressora e, se encontrar exatamente um toner ativo compatível com esse modelo e a cor, registra uma saída automática de uma unidade. Essa detecção depende das leituras SNMP e das compatibilidades cadastradas; a baixa pode deixar o saldo negativo.

### 3.4 Estoque de toners

- Consulta de toners ativos e opção para incluir inativos.
- Pesquisa por código ou modelo compatível na tabela de estoque, sem diferenciar letras maiúsculas ou acentos; o filtro continua aplicado após atualizar a tabela.
- Cadastro com marca, código, cor, modelos compatíveis, quantidade inicial e estoque mínimo. Marca/código/cor identificam o toner; ao cadastrar novamente um item existente, a quantidade informada é somada ao saldo.
- Ajuste manual de entrada ou saída ao clicar na quantidade em estoque de um toner ativo, com quantidade informada, confirmação e mensagem de resultado; exige permissão de ajuste. A retirada não pode superar o saldo disponível; os novos ajustes são registrados no histórico com o responsável.
- Registro de saída com quantidade, impressora/IP, patrimônio, responsável e observação. A saída altera o saldo e cria registros de movimentação/troca; não permite retirar toner inativo ou quantidade não positiva.
- Edição de modelos compatíveis e do estoque mínimo.
- Remoção lógica e reativação de toner, preservando o cadastro.
- Indicadores e filtros de estoque usam o saldo e o mínimo cadastrado para destacar itens que precisam de reposição.
- Às segundas-feiras a partir das 8h, o servidor envia uma sugestão simples de pedido para `EMAIL_ESTOQUE_SEMANAL`, com os toners e as quantidades positivas necessárias para atingir o mínimo, sem modelos de impressora ou saldos. Se não houver quantidades positivas, envia uma mensagem informativa. Nenhum pedido é realizado automaticamente.
- O servidor precisa estar em execução; se iniciar após as 8h de segunda-feira, tenta enviar naquele dia. Se permanecer desligado durante toda a segunda-feira, o resumo daquela semana não será enviado. Falhas são registradas em `monitor.log` e retentadas a cada cinco minutos. O registro de envio no banco evita envios repetidos na mesma semana; uma interrupção após o aceite pelo servidor de e-mail e antes do registro local pode causar duplicidade.
- Em **Estoque > Sugestões e pedidos**, a sugestão semanal fica disponível para revisão sem mostrar saldos ou modelos de impressora. Ela também permite ajustar itens que estão no mínimo e começam com quantidade zero; informe zero para não incluí-los no pedido. Uma pessoa com permissão de ajuste pode alterar as quantidades e confirmar seu registro como pedido; isso não envia uma compra ao fornecedor. Cada sugestão pode ser confirmada uma única vez. Confira pedidos pendentes para evitar registrar pedidos duplicados em semanas diferentes.
- A coluna **Impressoras compatíveis** estima quantos equipamentos cadastrados usam modelos ou famílias compatíveis com cada toner, incluindo os offline. Com permissão de monitoramento, clique na quantidade para ver nome, modelo, setor, patrimônio e IP. O mesmo equipamento pode aparecer em mais de um toner e a contagem não confirma o toner instalado; modelos não identificados não entram no cálculo.
- As quantidades ainda não confirmadas permanecem na tela ao trocar o filtro de estoque ou navegar entre seções, mas não são salvas ao recarregar ou fechar a página.
- Ao receber toners, informe as quantidades efetivamente recebidas no pedido e selecione **Adicionar recebimento ao estoque**. São aceitas entregas parciais até o total pedido; cada entrada é registrada no histórico com o responsável. Toners inativos precisam ser reativados antes do recebimento.

### 3.5 Histórico

A rota `/historico` retorna entradas, saídas manuais, saídas automáticas por detecção de troca e eventos de impressoras offline. As movimentações manuais são paginadas (limite configurável de 1 a 200, padrão 50); as saídas automáticas aparecem apenas na seção de trocas automáticas e são contadas uma vez. As contagens nas abas e seções consideram apenas os registros exibidos. A consulta de eventos offline considera os eventos registrados no dia atual.

O banco SQLite mantém as tabelas de toners, movimentações, trocas, níveis de toner e eventos offline. O histórico de retorno online também é gravado em `historico.json`.

### 3.6 Conferência do relatório PRINTER

- A conferência aceita um ou mais PDFs pesquisáveis, com limite total de upload de 10 MB e até 100 páginas por PDF. A análise não salva os arquivos automaticamente.
- Extrai número de série, modelo, local e identificador do equipamento; ignora itens identificados como scanners.
- Compara as séries e locais do PDF com o cadastro atual e aponta séries duplicadas, séries não encontradas, duplicidades no cadastro e divergências de local.
- Gera assunto e corpo de e-mail para revisão e cópia manual. **Essa função não envia o e-mail.**
- Permite aprovar equivalência entre nomes de locais, corrigir o local do cadastro, incluir um equipamento novo ou confirmar substituição quando a série muda e o IP permanece.
- Alterações aprovadas são gravadas em `ImpressorasRBS_atualizada.xlsx`; a planilha original é preservada. As equivalências aprovadas ficam em `.relatorio_locais_equivalentes.json`.
- As aprovações validam série/IP e recusam operações ambíguas, como série duplicada ou IP associado a vários registros.
- No histórico, o usuário salva um PDF por vez e pode baixá-lo novamente. O PDF original e os dados ficam no SQLite, sem criptografia adicional. O acesso exige a permissão de análise PRINTER.
- Os relatórios são identificados pelo centro de custo e competência; há um por mês para Saúde, Tesouro e Educação. Um PDF diferente para o mesmo setor e mês exige confirmação antes de substituir o anterior; um PDF idêntico não é duplicado.
- A comparação permite escolher dois meses e mostra a diferença por setor. Um relatório ausente é indicado como tal, não como zero.
- O gráfico de barras aparece na página inicial para usuários com permissão de análise PRINTER. Mostra os meses disponíveis lado a lado por setor, com valores e ausências também disponíveis em tabela. Um relatório ausente não é representado como zero.
- O total de páginas soma o consumo de cópias/impressões P&B e níveis de cor 1, 2 e 3, validando o resumo contra os detalhes. Scanner e outros serviços não entram. O consumo de página/metro linear é exibido separadamente, pois não representa uma quantidade identificável de páginas. Formatos ou serviços não reconhecidos são recusados para evitar totais incorretos.

## 4. Armazenamento e arquivos

| Arquivo | Uso identificado |
|---|---|
| `estoque.db` | Banco SQLite para estoque, usuários, convites, configuração, tokens, leituras de toner, movimentações, eventos e histórico PRINTER (incluindo PDFs). |
| `ImpressorasRBS.xlsx` | Planilha original do cadastro de impressoras. |
| `ImpressorasRBS_atualizada.xlsx` | Cadastro de trabalho preferencial; recebe alterações aprovadas/editadas pelo sistema. |
| `alertas_enviados.json` | Controle de alertas de toner já enviados. |
| `historico_toner_6.json` | Histórico diário de toner em 6%. |
| `impressoras_encontradas.json` | IPs que responderam na coleta. |
| `impressoras_offline.json` | Controle do início de indisponibilidade durante a coleta. |
| `historico.json` | Eventos de retorno online registrados pelo coletor. |
| `monitor.log` | Log de execução e erros. |
| `.env` | Fonte de configurações locais carregadas pelo módulo SNMP; não registrar nem compartilhar seus valores. |

## 5. Rotas principais

| Rota | Uso |
|---|---|
| `/entrar`, `/sair`, `/convite/<token>`, `/recuperar-admin` | Autenticação, ativação de convite, saída e recuperação administrativa local. |
| `/admin/usuarios` e rotas `/admin/...` | Gerenciamento de contas, permissões, convites e presença. |
| `/` e `/dados` | Interface e dados atualizados do monitoramento. |
| `/api/impressoras/editar`, `/api/impressoras/excluir` | Edição e exclusão lógica do cadastro. |
| `/api/impressoras/<ip>/contador` | Contador SNMP e compatibilidade de toner para a ficha do equipamento. |
| `/api/impressoras/<ip>/toners` | Toners compatíveis com o modelo cadastrado da impressora. |
| `/api/relatorio-impressoes` e `/api/relatorio-impressoes/excel` | Comparação mensal dos contadores e exportação em Excel. |
| `/estoque`, `/cadastrar-toner`, `/ajustar-estoque/<id>`, `/registrar-saida-toner` | Consulta, cadastro, ajuste e saída de toner. |
| `/remover-toner/<id>`, `/reativar-toner/<id>`, `/toner/<id>/...` | Gerenciamento de toner, compatibilidade e estoque mínimo. |
| `/historico`, `/toners-nao-confiaveis` | Histórico e consulta de toners classificados como não confiáveis. |
| `/api/relatorio-printer/...` | Análise e aprovação de equivalências, correções e inclusões/substituições. |

## 6. Configuração e execução

Dependências Python declaradas em [`requirements.txt`](./requirements.txt): Flask, openpyxl, pypdf, python-dotenv e pysnmp. A aplicação pode ser iniciada com `python app.py`; o código inicia o servidor na porta 5000 e escuta em todas as interfaces.

Configurações lidas pelo código:

- `PAINEL_SESSION_SECRET`: chave persistente das sessões; se ausente, o sistema mantém uma chave no banco.
- `PAINEL_REDE_LOCAL`: sub-rede autorizada opcional.
- `PAINEL_BASE_URL`: URL-base opcional para links de convite.
- `SNMP_COMMUNITY`: comunidade SNMP; o padrão no código é `public`.
- `EMAIL_SEMED`, `EMAIL_OUTROS`, `GMAIL_REMETENTE` e `GMAIL_SENHA_APP`: destinatários e credenciais usados para alertas automáticos.
- `EMAIL_ESTOQUE_SEMANAL`: destinatário do resumo semanal de estoque; usa o mesmo remetente e senha de aplicativo dos alertas.

O navegador carrega Tailwind CSS por CDN, além dos estilos locais; portanto, essa parte visual depende de acesso ao CDN.

## 7. Observações importantes

1. **Possível inconsistência nas colunas do cadastro:** o módulo principal e a comparação PRINTER usam a terceira coluna da planilha como número de série, enquanto o coletor SNMP interpreta essa coluna como patrimônio. Vale confirmar e padronizar o esquema do arquivo para evitar que patrimônio e série sejam exibidos/gravados de forma trocada.
2. O cookie de sessão está configurado com `SESSION_COOKIE_SECURE=False`. Se o painel for publicado por HTTPS, essa configuração deve ser revista.
3. O padrão `SNMP_COMMUNITY=public` deve ser substituído por uma comunidade apropriada ao ambiente.
4. `scripts/monitor_impressoras.py` contém dados de exemplo fixos e imprime níveis no terminal; não é o coletor de produção. O monitoramento integrado ao painel está em `suprimentos_snmp.py`. Os demais `scripts/teste_*.py` são utilitários de teste/diagnóstico.
5. Os testes existentes cobrem fluxos relevantes, mas não foram executados como parte da elaboração deste relatório.

## 8. Análise de aplicação e viabilidade

### 8.1 Possibilidades de aplicação

O sistema pode ser aplicado em organizações que mantêm várias impressoras conectadas à rede e precisam coordenar suporte técnico e reposição de suprimentos. Exemplos de ambientes adequados:

- secretarias e órgãos públicos com impressoras distribuídas por setores, unidades ou escolas;
- instituições de ensino que centralizam o acompanhamento de equipamentos e o estoque de toners;
- empresas privadas com parque de impressão compartilhado e equipe interna de TI ou patrimônio;
- prestadores de suporte que acompanham equipamentos de clientes, desde que sejam definidos controles de acesso e separação dos dados de cada organização.

Os principais usuários seriam profissionais de TI responsáveis pela disponibilidade e pelo cadastro dos equipamentos, equipes de almoxarifado/compras responsáveis pelos toners e gestores que consultam os indicadores e relatórios. A implantação depende de conectividade entre o servidor e as impressoras e de um cadastro confiável de equipamentos e suprimentos. O sistema atual é um painel organizacional, não uma aplicação voltada ao consumidor individual.

### 8.2 Benefícios oferecidos

Considerando como problema a dificuldade de acompanhar, em diferentes controles, o estado das impressoras, o consumo de suprimentos e a necessidade de reposição, a versão atual pode oferecer:

- **Visão centralizada:** reúne estado, níveis de suprimentos, localização e dados cadastrados das impressoras em um painel.
- **Identificação antecipada de necessidades:** destaca níveis baixos e envia alertas por e-mail quando as condições configuradas são atendidas.
- **Organização do estoque:** registra entradas e saídas, estoque mínimo, compatibilidades, sugestões de reposição e histórico de movimentações.
- **Redução de tarefas manuais:** automatiza consultas SNMP, coleta de contadores, alertas e a preparação de sugestões semanais de compra. A confirmação de um pedido continua sendo manual.
- **Apoio à conferência:** compara dados de relatórios PRINTER em PDF com o cadastro e permite revisar divergências antes de aprovar alterações.
- **Rastreabilidade e controle de acesso:** mantém histórico de operações e diferencia permissões por tipo de atividade.

Esses benefícios são capacidades previstas no sistema; ainda não há medição de economia de tempo, redução de custos ou taxa de erros em uso real. Além disso, níveis lidos por SNMP e estimativas de toner podem variar por equipamento e não substituem a conferência física.

### 8.3 Soluções semelhantes

#### HP Web Jetadmin

- **Finalidade principal:** administração centralizada de frotas de impressão e imagem.
- **Funcionalidades divulgadas:** descoberta de equipamentos, inclusive de diferentes marcas; monitoramento de estado e suprimentos; alertas configuráveis; agrupamento, configuração e solução de problemas; relatórios de uso e tendências.
- **Semelhanças:** consulta informações dos dispositivos pela rede, acompanha suprimentos e estado, e apresenta alertas e relatórios em uma ferramenta central.
- **Diferenças:** oferece recursos mais amplos de administração e configuração de dispositivos. O Monitor de Impressoras concentra-se nos fluxos descritos neste projeto: estoque de toners, histórico de movimentações, alertas específicos, contadores e conferência de relatórios PRINTER.
- **Fonte:** [HP Web Jetadmin — visão geral e funcionalidades](https://h20195.www2.hp.com/v2/GetDocument.aspx?docname=4AA5-2718ENW&cc=us&lc=en). A documentação de suporte da HP também descreve consultas SNMP e alertas de estado e suprimentos para dispositivos compatíveis: [gerenciamento de impressoras de terceiros](https://support.hp.com/ee-en/document/ish_3007439-2783374-16).

#### PaperCut MF

- **Finalidade principal:** gerenciamento de impressão e digitalização, com foco em controlar e acompanhar a atividade de usuários e dispositivos.
- **Funcionalidades divulgadas:** registro de atividades de impressão/cópia/digitalização, relatórios de uso, cotas e alocação de custos, impressão segura com liberação autenticada, implantação de filas e integração com fluxos de digitalização.
- **Semelhanças:** oferece gestão centralizada de dispositivos e relatórios relacionados à impressão, podendo apoiar organizações que precisam de visibilidade sobre sua operação de impressão.
- **Diferenças:** enfatiza trabalhos de impressão, usuários, segurança, cotas e custos. O sistema deste projeto não controla filas nem libera trabalhos de impressão; seu foco é acompanhar equipamentos e suprimentos, organizar o estoque e conferir dados PRINTER.
- **Fontes oficiais:** [PaperCut MF — produto](https://www.papercut.com/products/mf/) e [PaperCut MF/NG — funcionalidades](https://www.papercut.com/products/mf-ng/features/).

As funcionalidades acima são resumidas a partir das páginas dos próprios fornecedores, consultadas em 17 nov. 2026. A comparação é qualitativa e não representa teste de desempenho, avaliação de preço ou certificação de compatibilidade entre produtos.

### 8.4 Diferenciais do projeto

O diferencial mais concreto da solução é reunir, no mesmo painel, operações que frequentemente ficam em controles separados: monitoramento SNMP, cadastro de impressoras, movimentações de toner, sugestão de reposição, histórico e conferência de relatórios PRINTER. Isso permite relacionar o estado de um equipamento aos fluxos internos de estoque e de revisão cadastral.

Há também regras voltadas ao contexto operacional do projeto, como alertas por setor, tratamento de leituras de toner não confiáveis e sem chip, estimativas após registro de troca e análise de relatórios mensais por centro de custo. Esses recursos estão implementados conforme as limitações descritas neste relatório; não se afirma que sejam exclusivos no mercado. A diferenciação dependerá de validar com usuários reais se esses fluxos correspondem às rotinas da organização e se reduzem retrabalho.

### 8.5 Viabilidade da solução

| Aspecto | Análise |
|---|---|
| **Técnica** | A implementação utiliza tecnologias disponíveis e declaradas no projeto: Python, Flask, SQLite, openpyxl, pypdf e pysnmp. A coleta requer impressoras que respondam às consultas SNMP utilizadas. |
| **Infraestrutura** | Para uso interno, é necessário um computador ou servidor que mantenha a aplicação e o banco disponíveis, acesso de rede às impressoras pela porta SNMP, armazenamento e cópias de segurança. O envio de alertas depende de conta e serviço de e-mail configurados. A interface também carrega Tailwind CSS por CDN. |
| **Operação** | É necessário cadastrar e revisar impressoras e compatibilidades, configurar usuários e permissões, acompanhar falhas de coleta e e-mail, conferir sugestões de compra e orientar usuários. Não há integração automática com fornecedores para concluir compras. |
| **Recursos** | A continuidade demanda tempo de desenvolvimento e testes, administração de servidor e rede, suporte aos usuários e procedimentos de backup/recuperação. Também é preciso configurar segredos, HTTPS e comunidade SNMP apropriada antes de expor o sistema a usuários reais. |
| **Escalabilidade** | A arquitetura pode evoluir para atender mais unidades, mas a capacidade atual não foi medida. Antes de crescer, devem ser testados volume de impressoras e usuários, concorrência de consultas SNMP e comportamento dos agendadores. Uma implantação maior pode exigir banco de dados e execução de tarefas mais adequados a múltiplos processos, além de monitoramento e cópias de segurança centralizados. |

### 8.6 Disponibilização ou comercialização

O modelo mais direto para a versão atual é o **uso interno por uma organização**, hospedado em servidor acessível pela rede autorizada. A organização manteria a infraestrutura e a equipe responsável por suporte, atualização e cópias de segurança.

Se o projeto evoluir para produto, alternativas a avaliar incluem:

- **Licenciamento institucional:** instalação e suporte contratados por organização, com configuração para sua rede e cadastro;
- **Assinatura hospedada:** serviço gerenciado, desde que a arquitetura seja adaptada para isolamento entre organizações, segurança, disponibilidade e proteção dos dados;
- **Modelo gratuito com serviços pagos:** disponibilização do núcleo e cobrança por implantação, suporte, treinamento ou recursos adicionais, se isso for compatível com a estratégia e as licenças de todas as dependências.

Ainda não foram definidos preço, termos de licença do produto, níveis de serviço ou processo de suporte. Antes de comercializar, seria necessário validar a demanda, revisar licenças e dependências, formalizar responsabilidades sobre os dados e desenvolver uma instalação e atualização reproduzíveis. Não é adequado oferecer a versão atual como serviço público sem essa preparação.

### 8.7 Limitações atuais

- A aplicação e os agendadores foram descritos a partir do código e dos testes, mas não há comprovação neste relatório de operação contínua em ambiente de produção, carga suportada ou resultados de avaliação com usuários.
- O cadastro depende de planilhas Excel, e o relatório já aponta possível inconsistência na interpretação de colunas de série e patrimônio; o esquema precisa ser confirmado e padronizado.
- Leituras SNMP dependem de rede, resposta e suporte do equipamento. Níveis podem ficar indisponíveis ou ser estimados, e as estimativas não equivalem a uma medição física do toner.
- A configuração padrão de comunidade SNMP e `SESSION_COOKIE_SECURE=False`, apontadas neste relatório, precisam ser revistas antes de disponibilizar o sistema além de um ambiente controlado. A publicação exige HTTPS, gestão segura de segredos e revisão das permissões e da exposição de rede.
- O banco SQLite, arquivos JSON e arquivos de cadastro exigem rotina explícita de cópia de segurança, recuperação e controle de acesso ao servidor.
- O histórico de análises PRINTER pode armazenar PDFs sem criptografia adicional no banco; retenção e acesso aos documentos devem ser definidos pela organização.
- O sistema não realiza compras automaticamente, não envia o e-mail preparado pela conferência PRINTER e não substitui processos de aprovação da organização.
- A dependência de CDN para parte do estilo pode afetar a interface em redes sem acesso externo. A implantação também precisa validar os serviços externos de e-mail e os equipamentos usados.
- Ainda são necessários testes de carga, recuperação de falhas, implantação em ambiente-alvo e avaliação de usabilidade antes de afirmar prontidão para uso em larga escala.

### 8.8 Próximos passos prioritários

| Ação | Justificativa | Prioridade |
|---|---|---|
| Revisar segurança e preparar implantação HTTPS | Substituir configurações padrão sensíveis, revisar cookies, segredos, acesso de rede, permissões e armazenamento de documentos antes do uso por usuários reais. | Alta |
| Padronizar e validar o cadastro de impressoras | Resolver a interpretação de série e patrimônio e testar os dados com responsáveis pelo cadastro para evitar atualizações incorretas. | Alta |
| Executar piloto com usuários de TI e estoque | Validar os fluxos de monitoramento, saída/recebimento de toner, alertas e conferência PRINTER; registrar dificuldades e medir tarefas antes e depois. | Alta |
| Definir backup e recuperação | Criar e testar procedimentos para banco SQLite, planilhas e arquivos de controle, reduzindo risco de perda de histórico e configurações. | Alta |
| Ampliar testes de operação e carga | Simular falhas de rede/e-mail, maior quantidade de impressoras e concorrência; usar os resultados para decidir se é necessário alterar banco, coleta ou agendadores. | Média |
| Melhorar a interface com base no piloto | Priorizar ajustes de navegação e mensagens que sejam observados e registrados pelos usuários, em vez de mudanças sem validação. | Média |

### 8.9 Síntese da análise

- **Onde pode ser aplicada?** Em organizações com várias impressoras de rede, especialmente instituições de ensino, órgãos públicos e empresas com equipes de TI e estoque.
- **Que benefícios oferece?** Centraliza informações, sinaliza necessidades de suprimento, organiza movimentações e apoia a revisão de contadores e cadastros; os resultados ainda precisam ser medidos em piloto.
- **Que soluções semelhantes existem?** HP Web Jetadmin, voltado à administração centralizada de dispositivos, e PaperCut MF, voltado à gestão de impressão e digitalização.
- **Qual é o diferencial principal?** A integração, em um painel orientado ao contexto do projeto, entre monitoramento das impressoras, rotinas de estoque de toner e conferência de relatórios PRINTER.
- **O que é necessário para uso real?** Servidor e rede adequados, configuração segura, cadastro validado, backup, suporte operacional e piloto com usuários.
- **Quais são os próximos passos?** Priorizar segurança e implantação, padronizar o cadastro, realizar piloto e estabelecer recuperação de dados; depois, usar evidências para orientar melhorias e escalabilidade.
