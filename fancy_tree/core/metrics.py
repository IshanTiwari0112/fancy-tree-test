"""Code metrics and complexity analysis for fancy-tree."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from tree_sitter import Node, Parser

from ..schema import Symbol, SymbolType, FileInfo, RepoSummary
from .config import get_language_config
from .extraction import get_parser_for_language


@dataclass
class FunctionMetrics:
    """Metrics for a single function or method."""
    name: str
    line_start: int
    line_end: int
    lines_of_code: int
    cyclomatic_complexity: int
    parameter_count: int
    nesting_depth: int
    has_docstring: bool
    cognitive_complexity: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "lines_of_code": self.lines_of_code,
            "cyclomatic_complexity": self.cyclomatic_complexity,
            "parameter_count": self.parameter_count,
            "nesting_depth": self.nesting_depth,
            "has_docstring": self.has_docstring,
            "cognitive_complexity": self.cognitive_complexity
        }


@dataclass
class ClassMetrics:
    """Metrics for a class."""
    name: str
    line_start: int
    line_end: int
    lines_of_code: int
    method_count: int
    public_method_count: int
    private_method_count: int
    has_docstring: bool
    inheritance_depth: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "lines_of_code": self.lines_of_code,
            "method_count": self.method_count,
            "public_method_count": self.public_method_count,
            "private_method_count": self.private_method_count,
            "has_docstring": self.has_docstring,
            "inheritance_depth": self.inheritance_depth
        }


@dataclass
class FileMetrics:
    """Comprehensive metrics for a source file."""
    path: str
    language: str
    total_lines: int
    code_lines: int
    comment_lines: int
    blank_lines: int
    function_metrics: List[FunctionMetrics] = field(default_factory=list)
    class_metrics: List[ClassMetrics] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    complexity_score: float = 0.0
    maintainability_index: float = 0.0
    technical_debt_ratio: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "language": self.language,
            "total_lines": self.total_lines,
            "code_lines": self.code_lines,
            "comment_lines": self.comment_lines,
            "blank_lines": self.blank_lines,
            "function_metrics": [fm.to_dict() for fm in self.function_metrics],
            "class_metrics": [cm.to_dict() for cm in self.class_metrics],
            "imports": self.imports,
            "complexity_score": self.complexity_score,
            "maintainability_index": self.maintainability_index,
            "technical_debt_ratio": self.technical_debt_ratio
        }


@dataclass
class DependencyRelation:
    """Represents a dependency relationship between modules."""
    from_module: str
    to_module: str
    import_type: str  # 'import', 'from_import', 'relative_import'
    line_number: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_module": self.from_module,
            "to_module": self.to_module,
            "import_type": self.import_type,
            "line_number": self.line_number
        }


@dataclass
class TechnicalDebtIndicator:
    """Represents a technical debt indicator."""
    type: str  # 'complexity', 'duplication', 'size', 'documentation'
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    file_path: str
    line_number: Optional[int] = None
    suggestion: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "severity": self.severity,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "suggestion": self.suggestion
        }


class MetricsCalculator:
    """Main class for calculating code metrics and complexity."""
    
    def __init__(self):
        self.complexity_thresholds = {
            'function_complexity': {'low': 5, 'medium': 10, 'high': 15},
            'function_length': {'low': 20, 'medium': 50, 'high': 100},
            'parameter_count': {'low': 3, 'medium': 5, 'high': 8},
            'class_methods': {'low': 10, 'medium': 20, 'high': 30}
        }
    
    def calculate_file_metrics(self, file_path: Path, source_code: str, language: str) -> FileMetrics:
        """Calculate comprehensive metrics for a source file."""
        # Basic line counting
        lines = source_code.split('\n')
        total_lines = len(lines)
        blank_lines = sum(1 for line in lines if not line.strip())
        comment_lines = self._count_comment_lines(lines, language)
        code_lines = total_lines - blank_lines - comment_lines
        
        # Initialize file metrics
        file_metrics = FileMetrics(
            path=str(file_path),
            language=language,
            total_lines=total_lines,
            code_lines=code_lines,
            comment_lines=comment_lines,
            blank_lines=blank_lines
        )
        
        # Parse with tree-sitter for detailed analysis
        parser = get_parser_for_language(language)
        if parser:
            tree = parser.parse(source_code.encode('utf-8'))
            self._analyze_ast(tree.root_node, source_code, file_metrics, language)
        
        # Calculate derived metrics
        file_metrics.complexity_score = self._calculate_complexity_score(file_metrics)
        file_metrics.maintainability_index = self._calculate_maintainability_index(file_metrics)
        file_metrics.technical_debt_ratio = self._calculate_technical_debt_ratio(file_metrics)
        
        return file_metrics
    
    def _count_comment_lines(self, lines: List[str], language: str) -> int:
        """Count comment lines based on language-specific patterns."""
        comment_patterns = {
            'python': [r'^\s*#', r'^\s*"""', r'^\s*\'\'\''],
            'javascript': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
            'typescript': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
            'java': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
            'c': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
            'cpp': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
            'csharp': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
            'go': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
            'rust': [r'^\s*//', r'^\s*/\*', r'^\s*\*'],
            'php': [r'^\s*//', r'^\s*#', r'^\s*/\*'],
            'ruby': [r'^\s*#']
        }
        
        patterns = comment_patterns.get(language, [r'^\s*#', r'^\s*//'])
        comment_count = 0
        in_multiline_comment = False
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
                
            # Check for multiline comment start/end
            if '/*' in stripped:
                in_multiline_comment = True
            if '*/' in stripped:
                in_multiline_comment = False
                comment_count += 1
                continue
                
            if in_multiline_comment:
                comment_count += 1
                continue
                
            # Check single-line comment patterns
            for pattern in patterns:
                if re.match(pattern, line):
                    comment_count += 1
                    break
        
        return comment_count
    
    def _analyze_ast(self, node: Node, source_code: str, file_metrics: FileMetrics, language: str):
        """Analyze AST to extract detailed metrics."""
        config = get_language_config(language)
        if not config:
            return
        
        # Extract imports
        self._extract_imports(node, source_code, file_metrics, language)
        
        # Analyze functions and methods
        self._analyze_functions(node, source_code, file_metrics, config)
        
        # Analyze classes
        self._analyze_classes(node, source_code, file_metrics, config)
    
    def _extract_imports(self, node: Node, source_code: str, file_metrics: FileMetrics, language: str):
        """Extract import statements from the AST."""
        import_patterns = {
            'python': ['import_statement', 'import_from_statement'],
            'javascript': ['import_statement'],
            'typescript': ['import_statement'],
            'java': ['import_declaration'],
            'go': ['import_spec', 'import_declaration'],
            'rust': ['use_declaration'],
            'csharp': ['using_directive']
        }
        
        patterns = import_patterns.get(language, [])
        
        def visit_imports(n: Node):
            if n.type in patterns:
                import_text = self._get_node_text(n, source_code).strip()
                if import_text:
                    file_metrics.imports.append(import_text)
            
            for child in n.children:
                visit_imports(child)
        
        visit_imports(node)
    
    def _analyze_functions(self, node: Node, source_code: str, file_metrics: FileMetrics, config):
        """Analyze functions and methods in the AST."""
        def visit_functions(n: Node, nesting_level: int = 0):
            if n.type in config.function_nodes:
                metrics = self._calculate_function_metrics(n, source_code, nesting_level)
                if metrics:
                    file_metrics.function_metrics.append(metrics)
            
            for child in n.children:
                visit_functions(child, nesting_level + (1 if n.type in config.function_nodes else 0))
        
        visit_functions(node)
    
    def _analyze_classes(self, node: Node, source_code: str, file_metrics: FileMetrics, config):
        """Analyze classes in the AST."""
        def visit_classes(n: Node):
            if n.type in config.class_nodes:
                metrics = self._calculate_class_metrics(n, source_code, config)
                if metrics:
                    file_metrics.class_metrics.append(metrics)
            
            for child in n.children:
                visit_classes(child)
        
        visit_classes(node)
    
    def _calculate_function_metrics(self, node: Node, source_code: str, nesting_level: int) -> Optional[FunctionMetrics]:
        """Calculate detailed metrics for a function."""
        name = self._extract_function_name(node, source_code)
        if not name:
            return None
        
        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        lines_of_code = line_end - line_start + 1
        
        # Calculate cyclomatic complexity
        complexity = self._calculate_cyclomatic_complexity(node)
        
        # Count parameters
        param_count = self._count_parameters(node, source_code)
        
        # Check for docstring
        has_docstring = self._has_docstring(node, source_code)
        
        # Calculate cognitive complexity
        cognitive_complexity = self._calculate_cognitive_complexity(node, nesting_level)
        
        return FunctionMetrics(
            name=name,
            line_start=line_start,
            line_end=line_end,
            lines_of_code=lines_of_code,
            cyclomatic_complexity=complexity,
            parameter_count=param_count,
            nesting_depth=nesting_level,
            has_docstring=has_docstring,
            cognitive_complexity=cognitive_complexity
        )
    
    def _calculate_class_metrics(self, node: Node, source_code: str, config) -> Optional[ClassMetrics]:
        """Calculate detailed metrics for a class."""
        name = self._extract_class_name(node, source_code)
        if not name:
            return None
        
        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        lines_of_code = line_end - line_start + 1
        
        # Count methods
        method_count = 0
        public_method_count = 0
        private_method_count = 0
        
        def count_methods(n: Node):
            nonlocal method_count, public_method_count, private_method_count
            if n.type in config.function_nodes:
                method_count += 1
                method_name = self._extract_function_name(n, source_code)
                if method_name:
                    if method_name.startswith('_'):
                        private_method_count += 1
                    else:
                        public_method_count += 1
            
            for child in n.children:
                count_methods(child)
        
        count_methods(node)
        
        # Check for docstring
        has_docstring = self._has_docstring(node, source_code)
        
        return ClassMetrics(
            name=name,
            line_start=line_start,
            line_end=line_end,
            lines_of_code=lines_of_code,
            method_count=method_count,
            public_method_count=public_method_count,
            private_method_count=private_method_count,
            has_docstring=has_docstring
        )
    
    def _calculate_cyclomatic_complexity(self, node: Node) -> int:
        """Calculate cyclomatic complexity for a function."""
        complexity = 1  # Base complexity
        
        # Decision points that increase complexity
        decision_nodes = {
            'if_statement', 'elif_clause', 'else_clause',
            'while_statement', 'for_statement', 'for_in_statement',
            'try_statement', 'except_clause', 'catch_clause',
            'switch_statement', 'case_clause',
            'conditional_expression', 'ternary_expression',
            'and', 'or', '&&', '||'
        }
        
        def count_decisions(n: Node):
            nonlocal complexity
            if n.type in decision_nodes:
                complexity += 1
            
            for child in n.children:
                count_decisions(child)
        
        count_decisions(node)
        return complexity
    
    def _calculate_cognitive_complexity(self, node: Node, base_nesting: int) -> int:
        """Calculate cognitive complexity (more nuanced than cyclomatic)."""
        complexity = 0
        
        def calculate_recursive(n: Node, nesting_level: int):
            nonlocal complexity
            
            # Increment for control structures
            if n.type in ['if_statement', 'while_statement', 'for_statement']:
                complexity += 1 + nesting_level
                nesting_level += 1
            elif n.type in ['try_statement', 'catch_clause', 'except_clause']:
                complexity += 1 + nesting_level
            elif n.type in ['switch_statement', 'case_clause']:
                complexity += 1 + nesting_level
            elif n.type in ['and', 'or', '&&', '||']:
                complexity += 1
            
            for child in n.children:
                calculate_recursive(child, nesting_level)
        
        calculate_recursive(node, base_nesting)
        return complexity
    
    def _count_parameters(self, node: Node, source_code: str) -> int:
        """Count function parameters."""
        param_count = 0
        
        def count_params(n: Node):
            nonlocal param_count
            if n.type in ['parameter', 'parameter_list', 'formal_parameters']:
                # Count direct parameter children
                for child in n.children:
                    if child.type in ['identifier', 'parameter']:
                        param_count += 1
            
            for child in n.children:
                count_params(child)
        
        count_params(node)
        return param_count
    
    def _has_docstring(self, node: Node, source_code: str) -> bool:
        """Check if function/class has a docstring."""
        # Look for string literals at the beginning of the body
        for child in node.children:
            if child.type == 'block' or child.type == 'suite':
                for grandchild in child.children:
                    if grandchild.type in ['string', 'string_literal', 'expression_statement']:
                        text = self._get_node_text(grandchild, source_code).strip()
                        if text.startswith(('"""', "'''", '"', "'")):
                            return True
                break
        return False
    
    def _extract_function_name(self, node: Node, source_code: str) -> Optional[str]:
        """Extract function name from AST node."""
        for child in node.children:
            if child.type == 'identifier':
                return self._get_node_text(child, source_code)
        return None
    
    def _extract_class_name(self, node: Node, source_code: str) -> Optional[str]:
        """Extract class name from AST node."""
        for child in node.children:
            if child.type in ['identifier', 'type_identifier']:
                return self._get_node_text(child, source_code)
        return None
    
    def _get_node_text(self, node: Node, source_code: str) -> str:
        """Get text content of an AST node."""
        source_bytes = source_code.encode('utf-8')
        return source_bytes[node.start_byte:node.end_byte].decode('utf-8')
    
    def _calculate_complexity_score(self, file_metrics: FileMetrics) -> float:
        """Calculate overall complexity score for the file."""
        if not file_metrics.function_metrics:
            return 0.0
        
        total_complexity = sum(fm.cyclomatic_complexity for fm in file_metrics.function_metrics)
        avg_complexity = total_complexity / len(file_metrics.function_metrics)
        
        # Normalize to 0-100 scale
        return min(avg_complexity * 10, 100.0)
    
    def _calculate_maintainability_index(self, file_metrics: FileMetrics) -> float:
        """Calculate maintainability index (0-100, higher is better)."""
        if file_metrics.code_lines == 0:
            return 100.0
        
        # Simplified maintainability index calculation
        avg_complexity = file_metrics.complexity_score / 10
        comment_ratio = file_metrics.comment_lines / file_metrics.total_lines
        
        # Base score starts at 100
        score = 100.0
        score -= avg_complexity * 5  # Penalize complexity
        score += comment_ratio * 20  # Reward comments
        score -= (file_metrics.code_lines / 100) * 2  # Penalize large files
        
        return max(0.0, min(100.0, score))
    
    def _calculate_technical_debt_ratio(self, file_metrics: FileMetrics) -> float:
        """Calculate technical debt ratio (0-1, lower is better)."""
        debt_factors = 0.0
        total_factors = 0.0
        
        # High complexity functions
        for fm in file_metrics.function_metrics:
            total_factors += 1
            if fm.cyclomatic_complexity > self.complexity_thresholds['function_complexity']['high']:
                debt_factors += 1
            elif fm.cyclomatic_complexity > self.complexity_thresholds['function_complexity']['medium']:
                debt_factors += 0.5
        
        # Large functions
        for fm in file_metrics.function_metrics:
            if fm.lines_of_code > self.complexity_thresholds['function_length']['high']:
                debt_factors += 0.5
        
        # Functions without docstrings
        undocumented = sum(1 for fm in file_metrics.function_metrics if not fm.has_docstring)
        if file_metrics.function_metrics:
            debt_factors += (undocumented / len(file_metrics.function_metrics)) * 0.3
        
        return debt_factors / max(total_factors, 1)
    
    def generate_technical_debt_indicators(self, file_metrics: FileMetrics) -> List[TechnicalDebtIndicator]:
        """Generate technical debt indicators for a file."""
        indicators = []
        
        # High complexity functions
        for fm in file_metrics.function_metrics:
            if fm.cyclomatic_complexity > self.complexity_thresholds['function_complexity']['high']:
                indicators.append(TechnicalDebtIndicator(
                    type='complexity',
                    severity='high',
                    description=f"Function '{fm.name}' has high cyclomatic complexity ({fm.cyclomatic_complexity})",
                    file_path=file_metrics.path,
                    line_number=fm.line_start,
                    suggestion="Consider breaking this function into smaller, more focused functions"
                ))
            elif fm.cyclomatic_complexity > self.complexity_thresholds['function_complexity']['medium']:
                indicators.append(TechnicalDebtIndicator(
                    type='complexity',
                    severity='medium',
                    description=f"Function '{fm.name}' has moderate cyclomatic complexity ({fm.cyclomatic_complexity})",
                    file_path=file_metrics.path,
                    line_number=fm.line_start,
                    suggestion="Consider simplifying the logic or extracting helper functions"
                ))
        
        # Large functions
        for fm in file_metrics.function_metrics:
            if fm.lines_of_code > self.complexity_thresholds['function_length']['high']:
                indicators.append(TechnicalDebtIndicator(
                    type='size',
                    severity='high',
                    description=f"Function '{fm.name}' is very long ({fm.lines_of_code} lines)",
                    file_path=file_metrics.path,
                    line_number=fm.line_start,
                    suggestion="Consider breaking this function into smaller, more focused functions"
                ))
        
        # Functions with many parameters
        for fm in file_metrics.function_metrics:
            if fm.parameter_count > self.complexity_thresholds['parameter_count']['high']:
                indicators.append(TechnicalDebtIndicator(
                    type='complexity',
                    severity='medium',
                    description=f"Function '{fm.name}' has many parameters ({fm.parameter_count})",
                    file_path=file_metrics.path,
                    line_number=fm.line_start,
                    suggestion="Consider using a configuration object or reducing the number of parameters"
                ))
        
        # Missing documentation
        for fm in file_metrics.function_metrics:
            if not fm.has_docstring and fm.lines_of_code > 10:
                indicators.append(TechnicalDebtIndicator(
                    type='documentation',
                    severity='low',
                    description=f"Function '{fm.name}' lacks documentation",
                    file_path=file_metrics.path,
                    line_number=fm.line_start,
                    suggestion="Add a docstring explaining the function's purpose, parameters, and return value"
                ))
        
        # Large classes
        for cm in file_metrics.class_metrics:
            if cm.method_count > self.complexity_thresholds['class_methods']['high']:
                indicators.append(TechnicalDebtIndicator(
                    type='size',
                    severity='high',
                    description=f"Class '{cm.name}' has many methods ({cm.method_count})",
                    file_path=file_metrics.path,
                    line_number=cm.line_start,
                    suggestion="Consider splitting this class into smaller, more focused classes"
                ))
        
        return indicators


def calculate_repository_metrics(repo_summary: RepoSummary) -> Dict[str, Any]:
    """Calculate comprehensive metrics for an entire repository."""
    calculator = MetricsCalculator()
    all_file_metrics = []
    all_debt_indicators = []
    
    # Process each file in the repository
    def process_directory(dir_info):
        for file_info in dir_info.files:
            if file_info.language in ['python', 'javascript', 'typescript', 'java', 'go', 'rust', 'c', 'cpp']:
                try:
                    # Read file content
                    file_path = Path(file_info.path)
                    if file_path.exists():
                        source_code = file_path.read_text(encoding='utf-8')
                        
                        # Calculate metrics
                        metrics = calculator.calculate_file_metrics(file_path, source_code, file_info.language)
                        all_file_metrics.append(metrics)
                        
                        # Generate debt indicators
                        debt_indicators = calculator.generate_technical_debt_indicators(metrics)
                        all_debt_indicators.extend(debt_indicators)
                        
                except Exception as e:
                    print(f"Error processing {file_info.path}: {e}")
        
        # Process subdirectories
        for subdir in dir_info.subdirs:
            process_directory(subdir)
    
    process_directory(repo_summary.structure)
    
    # Calculate aggregate metrics
    total_functions = sum(len(fm.function_metrics) for fm in all_file_metrics)
    total_classes = sum(len(fm.class_metrics) for fm in all_file_metrics)
    total_code_lines = sum(fm.code_lines for fm in all_file_metrics)
    
    avg_complexity = 0.0
    if total_functions > 0:
        total_complexity = sum(
            sum(func.cyclomatic_complexity for func in fm.function_metrics)
            for fm in all_file_metrics
        )
        avg_complexity = total_complexity / total_functions
    
    avg_maintainability = 0.0
    if all_file_metrics:
        avg_maintainability = sum(fm.maintainability_index for fm in all_file_metrics) / len(all_file_metrics)
    
    # Categorize debt indicators by severity
    debt_by_severity = {'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
    for indicator in all_debt_indicators:
        debt_by_severity[indicator.severity] += 1
    
    return {
        'summary': {
            'total_files_analyzed': len(all_file_metrics),
            'total_functions': total_functions,
            'total_classes': total_classes,
            'total_code_lines': total_code_lines,
            'average_complexity': round(avg_complexity, 2),
            'average_maintainability': round(avg_maintainability, 2),
            'technical_debt_indicators': debt_by_severity
        },
        'file_metrics': [fm.to_dict() for fm in all_file_metrics],
        'debt_indicators': [di.to_dict() for di in all_debt_indicators],
        'top_complex_functions': sorted(
            [
                {'file': fm.path, 'function': func.name, 'complexity': func.cyclomatic_complexity}
                for fm in all_file_metrics
                for func in fm.function_metrics
            ],
            key=lambda x: x['complexity'],
            reverse=True
        )[:10],
        'largest_functions': sorted(
            [
                {'file': fm.path, 'function': func.name, 'lines': func.lines_of_code}
                for fm in all_file_metrics
                for func in fm.function_metrics
            ],
            key=lambda x: x['lines'],
            reverse=True
        )[:10]
    }
